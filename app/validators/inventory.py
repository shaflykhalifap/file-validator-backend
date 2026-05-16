"""
Inventory File Validator
- Tidak memvalidasi header sama sekali
- Mendukung 2 format:
  V1: Warehouse | ItemNumber | BalanceApproved | Modified_dt
  V2: StoreCode | SKU        | qty             | modified_dt
- Warning jika Modified_dt > 14 hari dari tanggal di nama file
- Pencarian kustom: kolom kedua (index 1)
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from app.core.config import settings

DATE_PATTERN  = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPECTED_COLS = 4


def _extract_date_from_filename(filename: str) -> datetime | None:
    """Ekstrak tanggal dari nama file. Contoh: MAP_IAB_EY02_20251107170125.txt -> 2025-11-07"""
    stem = re.sub(r'\.(txt|TXT)$', '', filename)
    # Cari 14 digit di akhir nama file
    m = re.search(r'(\d{14})$', stem)
    if m:
        try:
            return datetime.strptime(m.group(1), '%Y%m%d%H%M%S')
        except ValueError:
            pass
    # Fallback: 8 digit tanggal
    m8 = re.search(r'(\d{8})', stem)
    if m8:
        try:
            return datetime.strptime(m8.group(1), '%Y%m%d')
        except ValueError:
            pass
    return None


def validate_inventory_file(filepath: Path, filename: str = "") -> dict:
    errors = []
    fname  = filename or filepath.name
    raw    = filepath.read_bytes()

    if not raw.endswith(b"\n"):
        errors.append({"row": None, "column": None,
                        "message": "File tidak diakhiri dengan 1 baris kosong (enter) di bagian paling bawah."})
    elif raw.endswith(b"\n\n"):
        errors.append({"row": None, "column": None,
                        "message": "File memiliki lebih dari 1 baris kosong di bagian paling bawah."})

    text  = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    if not lines:
        return {"valid": False, "total_rows": 0,
                "errors": [{"row": None, "column": None, "message": "File kosong."}],
                "raw_lines": [], "header_version": "unknown", "header_cols": []}

    # Baca header untuk label kolom saja — TIDAK divalidasi apapun
    header_line = lines[0]
    if "\t" in header_line:
        header_cols = [h.strip() for h in header_line.split("\t")]
    else:
        # Header pakai spasi bukan tab — tetap baca untuk label, tidak error
        header_cols = [h.strip() for h in re.split(r'  +', header_line) if h.strip()]

    # Deteksi versi: kolom ke-2 (index 1)
    header_lower = [h.lower() for h in header_cols]
    if len(header_lower) > 1 and header_lower[1] == 'sku':
        header_version = 'v2'
    else:
        header_version = 'v1'

    # Kolom tanggal selalu di index 3
    date_col_idx   = 3
    date_col_label = header_cols[3] if len(header_cols) > 3 else 'Modified_dt'

    # Ekstrak tanggal dari nama file untuk warn 14 hari
    file_date = _extract_date_from_filename(fname)

    # Validasi isi — mulai dari baris ke-2 (index 1)
    data_lines = lines[1:]

    for line_idx, line in enumerate(data_lines):
        row_num = line_idx + 2

        if line == "":
            if line_idx < len(data_lines) - 1:
                errors.append({"row": row_num, "column": None,
                                "message": "Baris kosong ditemukan di tengah file."})
            continue

        # Cek tab di baris DATA (bukan header)
        if "\t" not in line:
            errors.append({"row": row_num, "column": None,
                            "message": (
                                f"Baris {row_num} tidak menggunakan Tab sebagai pemisah kolom. "
                                f"Periksa pemisah antara setiap nilai — pastikan bukan spasi biasa."
                            )})
            continue

        cols = line.split("\t")

        if len(cols) != EXPECTED_COLS:
            found_vals = " | ".join(f"'{c}'" for c in cols[:5])
            errors.append({"row": row_num, "column": None,
                            "message": (
                                f"Jumlah kolom tidak sesuai pada baris {row_num}. "
                                f"Ditemukan {len(cols)} kolom, seharusnya {EXPECTED_COLS}. "
                                f"Nilai ditemukan: {found_vals}."
                            )})
            continue

        # Cek spasi tersembunyi
        for idx, val in enumerate(cols):
            col_label = header_cols[idx] if idx < len(header_cols) else f"Kolom {idx + 1}"
            if val != val.rstrip():
                errors.append({"row": row_num, "column": col_label,
                                "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"})
            if val != val.lstrip():
                errors.append({"row": row_num, "column": col_label,
                                "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"})

        # Cek kolom balance/qty (index 2) harus integer
        if len(cols) > 2:
            bal_label = header_cols[2] if len(header_cols) > 2 else "Kolom 3"
            bal_clean = cols[2].strip()
            if bal_clean and not bal_clean.lstrip("-").isdigit():
                errors.append({"row": row_num, "column": bal_label,
                                "message": f"{bal_label} harus berupa angka bulat. Nilai: '{bal_clean}'"})

        # Validasi tanggal di kolom ke-4 (index 3)
        if date_col_idx < len(cols):
            dt_clean = cols[date_col_idx].strip()

            if not DATE_PATTERN.match(dt_clean):
                errors.append({"row": row_num, "column": date_col_label,
                                "message": (
                                    f"Format tanggal tidak valid, harus YYYY-MM-DD. "
                                    f"Nilai: '{dt_clean}'. Contoh yang benar: 2025-01-08"
                                )})
            else:
                try:
                    row_date = datetime.strptime(dt_clean, "%Y-%m-%d")
                except ValueError:
                    errors.append({"row": row_num, "column": date_col_label,
                                   "message": f"Tanggal tidak valid (bulan/hari di luar range). Nilai: '{dt_clean}'"})
                    row_date = None

                # WARN jika Modified_dt lebih dari 14 hari sebelum tanggal file
                if row_date is not None and file_date is not None:
                    selisih = (file_date.date() - row_date.date()).days
                    if selisih > 14:
                        errors.append({
                            "row": row_num,
                            "column": date_col_label,
                            "message": (
                                f"[WARN] Modified_dt lebih dari 14 hari dari tanggal file. "
                                f"Tanggal file: {file_date.strftime('%Y-%m-%d')} | "
                                f"Modified_dt: {dt_clean} | "
                                f"Selisih: {selisih} hari. "
                                f"Baris ini tidak akan terupdate di sistem."
                            ),
                            "level": "warn"
                        })

    real_errors = [e for e in errors if e.get("level") != "warn"]
    return {
        "valid": len(real_errors) == 0,
        "total_rows": len(data_lines),
        "errors": errors,
        "raw_lines": lines,
        "header_version": header_version,
        "header_cols": header_cols,
    }


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
