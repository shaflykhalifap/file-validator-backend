"""
Master Product File Validator
- Tidak memvalidasi header sama sekali
- Legal Entity Code TIDAK divalidasi
- Kolom PARENT/GENERIC/SPU, YEAR, SEASON boleh kosong
"""
from pathlib import Path
from typing import Optional
from app.core.config import settings

MASTER_HEADERS = [
    "UPC", "PARENT/GENERIC/SPU", "ARTICLE NUMBER/VARIANT/SKU",
    "BRAND CODE", "BRAND NAME", "PRODUCT NAME", "COLOR", "SIZE1",
    "YEAR", "SEASON", "CATEGORY", "SBU CODE", "LEGAL ENTITY CODE",
    "MAIN UPC", "DISCONTINUATION", "CONCEPT",
]
CONSUMED_COLUMNS = 14
NULLABLE_COLS    = {"PARENT/GENERIC/SPU", "YEAR", "SEASON"}


def validate_master_file(filepath: Path) -> dict:
    errors = []
    raw = filepath.read_bytes()

    if not raw.endswith(b"\n"):
        errors.append({"row": None, "column": None,
                        "message": "File tidak diakhiri dengan 1 baris kosong (enter) di bagian paling bawah."})
    elif raw.endswith(b"\n\n"):
        errors.append({"row": None, "column": None,
                        "message": "File memiliki lebih dari 1 baris kosong di bagian paling bawah."})

    content = raw.decode("utf-8", errors="replace")
    lines   = content.splitlines()

    if not lines:
        return {"valid": False, "total_rows": 0,
                "errors": [{"row": None, "column": None, "message": "File kosong."}],
                "raw_lines": []}

    # Header tidak divalidasi
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
                            "message": f"Baris {row_num} tidak menggunakan Tab sebagai pemisah kolom."})
            continue

        cols = line.split("\t")

        if len(cols) < 14:
            found_vals = " | ".join(f"'{c}'" for c in cols[:5])
            errors.append({"row": row_num, "column": None,
                            "message": (
                                f"Jumlah kolom tidak sesuai pada baris {row_num}. "
                                f"Ditemukan {len(cols)} kolom, seharusnya minimal 14. "
                                f"5 nilai pertama: {found_vals}."
                            )})
            continue

        while len(cols) < 16:
            cols.append("")

        # Kolom 15 & 16 harus kosong
        if cols[14].strip():
            errors.append({"row": row_num, "column": "DISCONTINUATION",
                            "message": f"Kolom 'DISCONTINUATION' seharusnya kosong. Ditemukan: '{cols[14].strip()}'."})
        if cols[15].strip():
            errors.append({"row": row_num, "column": "CONCEPT",
                            "message": f"Kolom 'CONCEPT' seharusnya kosong. Ditemukan: '{cols[15].strip()}'."})

        col_map = {MASTER_HEADERS[i]: cols[i] for i in range(16)}

        # Spasi tersembunyi
        for col_name in MASTER_HEADERS[:CONSUMED_COLUMNS]:
            val = col_map[col_name]
            if val != val.rstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"})
            if val != val.lstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"})

        # SKU harus mengandung SPU (hanya jika SPU tidak kosong)
        spu = col_map["PARENT/GENERIC/SPU"].strip()
        sku = col_map["ARTICLE NUMBER/VARIANT/SKU"].strip()
        if spu and sku and spu not in sku:
            errors.append({"row": row_num, "column": "ARTICLE NUMBER/VARIANT/SKU",
                            "message": (f"Nilai SKU harus mengandung nilai SPU. "
                                        f"SPU: '{spu}' | SKU: '{sku}'")})

        # UPC harus sama dengan MAIN UPC
        upc      = col_map["UPC"].strip()
        main_upc = col_map["MAIN UPC"].strip()
        if upc != main_upc:
            errors.append({"row": row_num, "column": "MAIN UPC",
                            "message": (f"Nilai UPC dan MAIN UPC harus identik. "
                                        f"UPC: '{upc}' | MAIN UPC: '{main_upc}'")})

        # Legal Entity Code: TIDAK divalidasi

        # Kolom wajib tidak boleh kosong (kecuali nullable)
        required_cols = [c for c in MASTER_HEADERS[:CONSUMED_COLUMNS] if c not in NULLABLE_COLS]
        for col_name in required_cols:
            if not col_map[col_name].strip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Kolom '{col_name}' tidak boleh kosong."})

    return {"valid": len(errors) == 0, "total_rows": len(data_lines),
            "errors": errors, "raw_lines": lines}


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
        for fp in sorted(files):
            result = validate_master_file(fp)
            result["file"] = fp.name
            result["folder"] = folder
            results.append(result)
    return results
