from pathlib import Path
from typing import Optional
from app.core.config import settings

MASTER_HEADERS = [
    "UPC", "PARENT/GENERIC/SPU", "ARTICLE NUMBER/VARIANT/SKU",
    "BRAND CODE", "BRAND NAME", "PRODUCT NAME", "COLOR", "SIZE1",
    "YEAR", "SEASON", "CATEGORY", "SBU CODE", "LEGAL ENTITY CODE",
    "MAIN UPC", "DISCONTINUATION", "CONCEPT",
]
CONSUMED_COLUMNS = 14  # hanya 14 kolom yang di-consume sistem


def validate_master_file(filepath: Path) -> dict:
    errors = []
    raw = filepath.read_bytes()

    # 1. Trailing newline
    if not raw.endswith(b"\n"):
        errors.append({"row": None, "column": None,
                        "message": "File tidak diakhiri dengan 1 baris kosong (enter) di bagian paling bawah."})
    elif raw.endswith(b"\n\n"):
        errors.append({"row": None, "column": None,
                        "message": "File memiliki lebih dari 1 baris kosong di bagian paling bawah."})

    content = raw.decode("utf-8", errors="replace")
    lines = content.splitlines()

    if not lines:
        return {"valid": False, "total_rows": 0,
                "errors": [{"row": None, "column": None, "message": "File kosong."}]}

    # 2. Validasi header
    header_line = lines[0]
    headers = header_line.split("\t")
    headers_stripped = [h.strip() for h in headers]

    if headers_stripped != MASTER_HEADERS:
        errors.append({
            "row": 1, "column": None,
            "message": f"Header tidak sesuai.\nDitemukan : {headers_stripped}\nSeharusnya: {MASTER_HEADERS}"
        })
        return {"valid": False, "total_rows": len(lines) - 1, "errors": errors}

    if len(headers) != 16:
        errors.append({"row": 1, "column": None,
                        "message": f"Jumlah header harus 16. Ditemukan: {len(headers)}"})

    for i, h in enumerate(headers):
        if h != h.strip():
            errors.append({"row": 1, "column": MASTER_HEADERS[i] if i < len(MASTER_HEADERS) else f"Kolom {i+1}",
                            "message": f"Header '{h}' mengandung spasi di awal atau akhir."})

    # 3. Validasi baris data
    data_lines = lines[1:]
    for line_idx, line in enumerate(data_lines):
        row_num = line_idx + 2

        if line == "":
            if line_idx < len(data_lines) - 1:
                errors.append({"row": row_num, "column": None,
                                "message": "Baris kosong ditemukan di tengah file."})
            continue

        if "\t" not in line:
            errors.append({"row": row_num, "column": None,
                            "message": "Pemisah kolom bukan Tab pada baris ini."})
            continue

        cols = line.split("\t")

        if len(cols) != 16:
            errors.append({"row": row_num, "column": None,
                            "message": f"Jumlah kolom tidak sesuai. Ditemukan {len(cols)}, seharusnya 16."})
            continue

        col_map = {MASTER_HEADERS[i]: cols[i] for i in range(16)}

        # Cek trailing/leading spasi untuk 14 kolom yang di-consume
        for col_name in MASTER_HEADERS[:CONSUMED_COLUMNS]:
            val = col_map[col_name]
            if val != val.rstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"})
            if val != val.lstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"})

        # Cek SKU harus mengandung SPU
        spu = col_map["PARENT/GENERIC/SPU"].strip()
        sku = col_map["ARTICLE NUMBER/VARIANT/SKU"].strip()
        if spu and sku and spu not in sku:
            errors.append({"row": row_num, "column": "ARTICLE NUMBER/VARIANT/SKU",
                            "message": f"SKU harus mengandung nilai SPU. SPU: '{spu}' | SKU: '{sku}'"})

        # Cek UPC == MAIN UPC
        upc = col_map["UPC"].strip()
        main_upc = col_map["MAIN UPC"].strip()
        if upc != main_upc:
            errors.append({"row": row_num, "column": "MAIN UPC",
                            "message": f"UPC dan MAIN UPC harus sama. UPC: '{upc}' | MAIN UPC: '{main_upc}'"})

        # Cek LEGAL ENTITY CODE: 4 digit angka
        legal = col_map["LEGAL ENTITY CODE"].strip()
        if not (legal.isdigit() and len(legal) == 4):
            errors.append({"row": row_num, "column": "LEGAL ENTITY CODE",
                            "message": f"LEGAL ENTITY CODE harus tepat 4 digit angka. Nilai: '{legal}'"})

        # Cek UPC tidak kosong
        if not upc:
            errors.append({"row": row_num, "column": "UPC",
                            "message": "UPC tidak boleh kosong."})

        # Cek kolom wajib lainnya tidak kosong (14 kolom consumed, kecuali DISCONTINUATION & CONCEPT)
        required_cols = MASTER_HEADERS[:CONSUMED_COLUMNS - 2]  # exclude DISCONTINUATION & CONCEPT
        for col_name in required_cols:
            if not col_map[col_name].strip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Kolom '{col_name}' tidak boleh kosong."})

    return {"valid": len(errors) == 0, "total_rows": len(data_lines), "errors": errors}


def run_master_validation(folder: str, filename: Optional[str] = None) -> list[dict]:
    base = settings.INBOX_DIR if folder == "inbox" else settings.ERROR_DIR
    results = []

    if filename:
        fp = base / filename
        if not fp.exists():
            return [{"file": filename, "valid": False, "total_rows": 0, "folder": folder,
                     "errors": [{"row": None, "column": None,
                                 "message": f"File '{filename}' tidak ditemukan di folder {folder}."}]}]
        result = validate_master_file(fp)
        result["file"] = filename
        result["folder"] = folder
        results.append(result)
    else:
        files = list(base.glob("*.txt"))
        if not files:
            return [{"file": None, "valid": True, "total_rows": 0, "folder": folder,
                     "errors": [{"row": None, "column": None,
                                 "message": f"Tidak ada file .txt di folder {folder}."}]}]
        for fp in files:
            result = validate_master_file(fp)
            result["file"] = fp.name
            result["folder"] = folder
            results.append(result)

    return results
