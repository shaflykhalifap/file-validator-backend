import re
from pathlib import Path
from typing import Optional
from app.core.config import settings

INVENTORY_HEADERS = ["Warehouse", "ItemNumber", "BalanceApproved", "Modified_dt"]
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_inventory_file(filepath: Path) -> dict:
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

    if headers_stripped != INVENTORY_HEADERS:
        errors.append({
            "row": 1, "column": None,
            "message": f"Header tidak sesuai. Ditemukan: {headers} | Seharusnya: {INVENTORY_HEADERS}"
        })
        return {"valid": False, "total_rows": len(lines) - 1, "errors": errors}

    for i, h in enumerate(headers):
        if h != h.strip():
            errors.append({"row": 1, "column": INVENTORY_HEADERS[i],
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
        if len(cols) != 4:
            errors.append({"row": row_num, "column": None,
                            "message": f"Jumlah kolom tidak sesuai. Ditemukan {len(cols)}, seharusnya 4."})
            continue

        warehouse, item_number, balance, modified_dt = cols
        col_map = {
            "Warehouse": warehouse,
            "ItemNumber": item_number,
            "BalanceApproved": balance,
            "Modified_dt": modified_dt,
        }

        # Cek trailing/leading spasi
        for col_name, val in col_map.items():
            if val != val.rstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"})
            if val != val.lstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"})

        # Cek Modified_dt format YYYY-MM-DD
        dt_clean = modified_dt.strip()
        if not DATE_PATTERN.match(dt_clean):
            errors.append({"row": row_num, "column": "Modified_dt",
                            "message": f"Format tanggal tidak valid, harus YYYY-MM-DD. Nilai: '{dt_clean}'"})
        else:
            # Validasi tanggal yang masuk akal
            try:
                from datetime import datetime
                datetime.strptime(dt_clean, "%Y-%m-%d")
            except ValueError:
                errors.append({"row": row_num, "column": "Modified_dt",
                                "message": f"Tanggal tidak valid (misal bulan/hari di luar range). Nilai: '{dt_clean}'"})

        # Cek BalanceApproved harus angka bulat
        bal_clean = balance.strip()
        if not bal_clean.lstrip("-").isdigit():
            errors.append({"row": row_num, "column": "BalanceApproved",
                            "message": f"BalanceApproved harus berupa angka bulat. Nilai: '{bal_clean}'"})

    return {"valid": len(errors) == 0, "total_rows": len(data_lines), "errors": errors}


def run_inventory_validation(folder: str, filename: Optional[str] = None) -> list[dict]:
    base = settings.INBOX_DIR if folder == "inbox" else settings.ERROR_DIR
    results = []

    if filename:
        fp = base / filename
        if not fp.exists():
            return [{"file": filename, "valid": False, "total_rows": 0, "folder": folder,
                     "errors": [{"row": None, "column": None,
                                 "message": f"File '{filename}' tidak ditemukan di folder {folder}."}]}]
        result = validate_inventory_file(fp)
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
            result = validate_inventory_file(fp)
            result["file"] = fp.name
            result["folder"] = folder
            results.append(result)

    return results
