from pathlib import Path
from typing import Optional
from app.core.config import settings

PRICE_HEADERS = [
    "PARENT / GENERIC / SPU",
    "LEGAL ENTITY CODE",
    "ARTICLE NUMBER / VARIANT / SKU",
    "LIST PRICE",
    "CURRENT PRICE",
]

def validate_price_file(filepath: Path) -> dict:
    """
    Validasi file Price berdasarkan aturan yang ditentukan.
    Mengembalikan dict berisi status valid/invalid dan list error detail.
    """
    errors = []
    raw = filepath.read_bytes()

    # 1. Cek trailing newline (1 enter di akhir file)
    if not raw.endswith(b"\n"):
        errors.append({
            "row": None,
            "column": None,
            "message": "File tidak diakhiri dengan 1 baris kosong (enter) di bagian paling bawah."
        })
    elif raw.endswith(b"\n\n"):
        errors.append({
            "row": None,
            "column": None,
            "message": "File memiliki lebih dari 1 baris kosong di bagian paling bawah."
        })

    content = raw.decode("utf-8", errors="replace")
    lines = content.splitlines()

    if not lines:
        return {"valid": False, "total_rows": 0, "errors": [{"row": None, "column": None, "message": "File kosong."}]}

    # 2. Validasi header
    header_line = lines[0]
    headers = header_line.split("\t")
    headers_stripped = [h.strip() for h in headers]

    if headers_stripped != PRICE_HEADERS:
        errors.append({
            "row": 1,
            "column": None,
            "message": f"Header tidak sesuai. Ditemukan: {headers} | Seharusnya: {PRICE_HEADERS}"
        })
        # Kalau header salah, validasi baris data jadi tidak relevan
        return {"valid": False, "total_rows": len(lines) - 1, "errors": errors}

    # Cek spasi di header
    for i, h in enumerate(headers):
        if h != h.strip():
            errors.append({
                "row": 1,
                "column": PRICE_HEADERS[i] if i < len(PRICE_HEADERS) else f"Kolom {i+1}",
                "message": f"Header kolom '{h}' mengandung spasi di awal atau akhir."
            })

    # Cek pemisah header — harus Tab
    if "\t" not in header_line and len(PRICE_HEADERS) > 1:
        errors.append({"row": 1, "column": None, "message": "Pemisah kolom pada header bukan Tab."})

    # 3. Validasi tiap baris data
    data_lines = lines[1:]
    for line_idx, line in enumerate(data_lines):
        row_num = line_idx + 2  # baris 1 = header

        # Skip baris kosong di akhir (1 enter diperbolehkan)
        if line == "":
            if line_idx < len(data_lines) - 1:
                errors.append({"row": row_num, "column": None, "message": "Baris kosong ditemukan di tengah file."})
            continue

        # Cek pemisah kolom harus Tab
        if "\t" not in line:
            errors.append({"row": row_num, "column": None, "message": "Pemisah kolom bukan Tab pada baris ini."})
            continue

        cols = line.split("\t")

        # Cek jumlah kolom
        if len(cols) != 5:
            errors.append({
                "row": row_num,
                "column": None,
                "message": f"Jumlah kolom tidak sesuai. Ditemukan {len(cols)} kolom, seharusnya 5."
            })
            continue

        spu, legal, sku, list_price, curr_price = cols
        col_map = {
            "PARENT / GENERIC / SPU": spu,
            "LEGAL ENTITY CODE": legal,
            "ARTICLE NUMBER / VARIANT / SKU": sku,
            "LIST PRICE": list_price,
            "CURRENT PRICE": curr_price,
        }

        # Cek trailing space tiap cell
        for col_name, val in col_map.items():
            if val != val.rstrip():
                errors.append({
                    "row": row_num,
                    "column": col_name,
                    "message": f"Terdapat spasi di akhir cell. Nilai cell: '{val}'"
                })
            if val != val.lstrip():
                errors.append({
                    "row": row_num,
                    "column": col_name,
                    "message": f"Terdapat spasi di awal cell. Nilai cell: '{val}'"
                })

        # Cek LEGAL ENTITY CODE: tepat 4 digit angka
        legal_clean = legal.strip()
        if not (legal_clean.isdigit() and len(legal_clean) == 4):
            errors.append({
                "row": row_num,
                "column": "LEGAL ENTITY CODE",
                "message": f"LEGAL ENTITY CODE harus tepat 4 digit angka. Nilai ditemukan: '{legal_clean}'"
            })

        # Cek LIST PRICE: angka, desimal pakai titik bukan koma
        list_price_clean = list_price.strip()
        if "," in list_price_clean:
            errors.append({
                "row": row_num,
                "column": "LIST PRICE",
                "message": f"LIST PRICE menggunakan koma sebagai desimal, seharusnya titik. Nilai: '{list_price_clean}'"
            })
        else:
            try:
                float(list_price_clean)
            except ValueError:
                errors.append({
                    "row": row_num,
                    "column": "LIST PRICE",
                    "message": f"LIST PRICE bukan angka valid. Nilai: '{list_price_clean}'"
                })

        # Cek CURRENT PRICE
        curr_price_clean = curr_price.strip()
        if "," in curr_price_clean:
            errors.append({
                "row": row_num,
                "column": "CURRENT PRICE",
                "message": f"CURRENT PRICE menggunakan koma sebagai desimal, seharusnya titik. Nilai: '{curr_price_clean}'"
            })
        else:
            try:
                float(curr_price_clean)
            except ValueError:
                errors.append({
                    "row": row_num,
                    "column": "CURRENT PRICE",
                    "message": f"CURRENT PRICE bukan angka valid. Nilai: '{curr_price_clean}'"
                })

    return {
        "valid": len(errors) == 0,
        "total_rows": len(data_lines),
        "errors": errors
    }


def run_price_validation(folder: str, filename: Optional[str] = None) -> list[dict]:
    """
    Jalankan validasi untuk folder inbox atau error.
    Jika filename diisi, validasi 1 file. Jika kosong, validasi semua file.
    """
    base = settings.INBOX_DIR if folder == "inbox" else settings.ERROR_DIR
    results = []

    if filename:
        fp = base / filename
        if not fp.exists():
            return [{"file": filename, "valid": False, "total_rows": 0,
                     "errors": [{"row": None, "column": None, "message": f"File '{filename}' tidak ditemukan di folder {folder}."}]}]
        result = validate_price_file(fp)
        result["file"] = filename
        result["folder"] = folder
        results.append(result)
    else:
        files = list(base.glob("*.txt"))
        if not files:
            return [{"file": None, "valid": True, "total_rows": 0, "folder": folder,
                     "errors": [{"row": None, "column": None, "message": f"Tidak ada file .txt di folder {folder}."}]}]
        for fp in files:
            result = validate_price_file(fp)
            result["file"] = fp.name
            result["folder"] = folder
            results.append(result)

    return results
