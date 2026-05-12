import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from app.core.config import settings


def _extract_date_from_filename(filename: str) -> datetime | None:
    """
    Ekstrak tanggal dari nama file inventory.
    Format akhiran: YYYYMMDDHHMMSS
    Contoh: MAP_Inv_TL00_20260505200301.txt → 2026-05-05
    """
    # Cari pola 14 digit angka di akhir nama file (sebelum .txt)
    stem = filename.replace('.txt', '').replace('.TXT', '')
    match = re.search(r'(\d{14})$', stem)
    if match:
        ts = match.group(1)
        try:
            return datetime.strptime(ts, '%Y%m%d%H%M%S')
        except ValueError:
            pass
    # Fallback: cari 8 digit tanggal saja
    match8 = re.search(r'(\d{8})', stem)
    if match8:
        try:
            return datetime.strptime(match8.group(1), '%Y%m%d')
        except ValueError:
            pass
    return None

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


def validate_inventory_file(filepath: Path, filename: str = "") -> dict:
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

    # 2. Header tidak divalidasi untuk inventory
    # Dua format header yang valid:
    # V1: Warehouse, ItemNumber, BalanceApproved, Modified_dt
    # V2: StoreCode, SKU, qty, modified_dt
    # Deteksi format dari baris header untuk keperluan info saja
    header_line = lines[0]
    header_cols = [h.strip() for h in header_line.split("\t")]
    # Deteksi versi header (untuk dipass ke result)
    if any(h.lower() == 'sku' for h in header_cols):
        header_version = 'v2'  # StoreCode, SKU, qty, modified_dt
        date_col_name  = 'modified_dt'
        date_col_idx   = next((i for i, h in enumerate(header_cols) if h.lower() == 'modified_dt'), 3)
    else:
        header_version = 'v1'  # Warehouse, ItemNumber, BalanceApproved, Modified_dt
        date_col_name  = 'Modified_dt'
        date_col_idx   = next((i for i, h in enumerate(header_cols) if h.lower() == 'modified_dt'), 3)

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

        # Validasi spasi di semua kolom (gunakan nama dari header asli jika ada)
        for idx, val in enumerate(cols):
            col_label = header_cols[idx] if idx < len(header_cols) else f"Kolom {idx+1}"
            if val != val.rstrip():
                errors.append({"row": row_num, "column": col_label,
                                "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"})
            if val != val.lstrip():
                errors.append({"row": row_num, "column": col_label,
                                "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"})

        # Ambil kolom tanggal berdasarkan posisi yang terdeteksi
        modified_dt = cols[date_col_idx] if date_col_idx < len(cols) else ''
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
                row_date = datetime.strptime(dt_clean, "%Y-%m-%d")
            except ValueError:
                errors.append({"row": row_num, "column": "Modified_dt",
                                "message": f"Tanggal tidak valid (bulan/hari di luar range). Nilai: '{dt_clean}'"})
                row_date = None

            # Validasi: Modified_dt tidak boleh lebih dari 14 hari
            # sebelum tanggal di nama file
            if row_date is not None:
                file_date = _extract_date_from_filename(filename or filepath.name)
                if file_date is not None:
                    selisih = (file_date.date() - row_date.date()).days
                    if selisih > 14:
                        errors.append({
                            "row": row_num,
                            "column": "Modified_dt",
                            "message": (
                                f"[WARN] Modified_dt lebih dari 14 hari dari tanggal file. "
                                f"Tanggal file: {file_date.strftime('%Y-%m-%d')} | "
                                f"Modified_dt: {dt_clean} | "
                                f"Selisih: {selisih} hari. "
                                f"Baris ini tidak akan terupdate di sistem."
                            ),
                            "level": "warn"
                        })

        # Validasi kolom balance/qty (kolom ke-3, index 2) harus bilangan bulat
        if len(cols) > 2:
            bal_label = header_cols[2] if len(header_cols) > 2 else 'Kolom 3'
            bal_clean = cols[2].strip()
            if not bal_clean.lstrip("-").isdigit():
                errors.append({"row": row_num, "column": bal_label,
                                "message": f"{bal_label} harus berupa angka bulat. Nilai: '{bal_clean}'"})

    return {"valid": len(errors) == 0, "total_rows": len(data_lines), "errors": errors, "raw_lines": lines, "header_version": header_version, "header_cols": header_cols}


def run_inventory_validation(folder: str, filename: Optional[str] = None) -> list[dict]:
    base = settings.INBOX_DIR if folder == "inbox" else settings.ERROR_DIR
    results = []
    if filename:
        fp = base / filename
        if not fp.exists():
            return [{"file": filename, "valid": False, "total_rows": 0, "folder": folder,
                     "errors": [{"row": None, "column": None,
                                 "message": f"File '{filename}' tidak ditemukan di folder {folder}."}]}]
        result = validate_inventory_file(fp, filename=fp.name)
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
            result = validate_inventory_file(fp, filename=fp.name)
            result["file"] = fp.name
            result["folder"] = folder
            results.append(result)
    return results
