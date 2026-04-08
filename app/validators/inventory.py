import re
from pathlib import Path
from typing import Optional
from app.core.config import settings

INVENTORY_HEADERS = ["Warehouse", "ItemNumber", "BalanceApproved", "Modified_dt"]
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _analyze_header_errors(found: list[str], expected: list[str], row: int) -> list[dict]:
    errors = []
    if len(found) != len(expected):
        errors.append({
            "row": row, "column": None,
            "message": (
                f"Jumlah kolom header tidak sesuai. "
                f"Ditemukan {len(found)} kolom, seharusnya {len(expected)} kolom. "
                f"Kemungkinan penyebab: ada kolom yang hilang atau pemisah header bukan Tab."
            )
        })
    check_count = min(len(found), len(expected))
    for i in range(check_count):
        f = found[i]
        e = expected[i]
        f_stripped = f.strip()
        if f_stripped == e:
            if f != f_stripped:
                errors.append({"row": row, "column": f"Kolom {i+1}",
                                "message": f"Header kolom {i+1} ('{e}') mengandung spasi di awal atau akhir."})
        else:
            if f_stripped.lower() == e.lower():
                errors.append({
                    "row": row, "column": f"Kolom {i+1}",
                    "message": (
                        f"Nama header kolom {i+1} tidak sesuai kapitalisasi (case-sensitive). "
                        f"Ditemukan: '{f_stripped}' | Seharusnya: '{e}' "
                        f"(perhatikan camelCase — huruf kapital di setiap kata)"
                    )
                })
            elif f_stripped.replace(" ", "") == e.replace(" ", ""):
                errors.append({
                    "row": row, "column": f"Kolom {i+1}",
                    "message": (
                        f"Header kolom {i+1} kemungkinan menggunakan spasi alih-alih Tab sebagai pemisah. "
                        f"Ditemukan: '{f_stripped}' | Seharusnya: '{e}'"
                    )
                })
            else:
                errors.append({
                    "row": row, "column": f"Kolom {i+1}",
                    "message": f"Nama header kolom {i+1} salah. Ditemukan: '{f_stripped}' | Seharusnya: '{e}'"
                })
    return errors


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

    # 2. Validasi header — TIDAK berhenti meski salah
    header_line = lines[0]

    if "\t" not in header_line and len(INVENTORY_HEADERS) > 1:
        errors.append({"row": 1, "column": None,
                        "message": "Pemisah antar kolom pada baris header bukan Tab. Pastikan menggunakan karakter Tab untuk memisahkan kolom."})
        headers = [h.strip() for h in header_line.split("  ") if h.strip()]
    else:
        headers = header_line.split("\t")

    headers_stripped = [h.strip() for h in headers]

    if headers_stripped != INVENTORY_HEADERS:
        header_errors = _analyze_header_errors(headers, INVENTORY_HEADERS, 1)
        errors.extend(header_errors)
    else:
        for i, h in enumerate(headers):
            if h != h.strip():
                errors.append({"row": 1, "column": INVENTORY_HEADERS[i],
                                "message": f"Header kolom '{INVENTORY_HEADERS[i]}' mengandung spasi di awal atau akhir."})

    # 3. Validasi isi — SELALU dijalankan
    data_lines = lines[1:]
    for line_idx, line in enumerate(data_lines):
        row_num = line_idx + 2

        if line == "":
            if line_idx < len(data_lines) - 1:
                errors.append({"row": row_num, "column": None,
                                "message": "Baris kosong ditemukan di tengah file."})
            continue

        if "\t" not in line:
            errors.append({
                "row": row_num, "column": None,
                "message": (
                    f"Baris {row_num} tidak menggunakan Tab sebagai pemisah kolom. "
                    f"Periksa pemisah antara setiap nilai — pastikan bukan spasi biasa."
                )
            })
            continue

        cols = line.split("\t")

        if len(cols) != 4:
            found_vals = " | ".join(f"'{c}'" for c in cols[:5])
            errors.append({
                "row": row_num, "column": None,
                "message": (
                    f"Jumlah kolom tidak sesuai pada baris {row_num}. "
                    f"Ditemukan {len(cols)} kolom, seharusnya 4. "
                    f"Nilai yang ditemukan: {found_vals}. "
                    f"Kemungkinan: ada kolom yang hilang atau pemisah antar nilai bukan Tab."
                )
            })
            continue

        warehouse, item_number, balance, modified_dt = cols
        col_map = {
            "Warehouse": warehouse,
            "ItemNumber": item_number,
            "BalanceApproved": balance,
            "Modified_dt": modified_dt,
        }

        for col_name, val in col_map.items():
            if val != val.rstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"})
            if val != val.lstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"})

        dt_clean = modified_dt.strip()
        if not DATE_PATTERN.match(dt_clean):
            errors.append({"row": row_num, "column": "Modified_dt",
                            "message": (
                                f"Format tanggal tidak valid, harus YYYY-MM-DD. "
                                f"Nilai: '{dt_clean}'. "
                                f"Contoh yang benar: 2025-01-08"
                            )})
        else:
            try:
                from datetime import datetime
                datetime.strptime(dt_clean, "%Y-%m-%d")
            except ValueError:
                errors.append({"row": row_num, "column": "Modified_dt",
                                "message": f"Tanggal tidak valid (bulan/hari di luar range). Nilai: '{dt_clean}'"})

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
        for fp in sorted(files):
            result = validate_inventory_file(fp)
            result["file"] = fp.name
            result["folder"] = folder
            results.append(result)
    return results
