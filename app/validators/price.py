"""
Price File Validator
- Tidak memvalidasi header
- 5 kolom, semua wajib tidak kosong (termasuk Legal Entity, bebas format)
- Legal Entity Code tidak divalidasi formatnya
- Desimal LIST PRICE dan CURRENT PRICE harus pakai titik
- Pencarian kustom: kolom pertama (index 0)
"""
import re
from pathlib import Path
from typing import Optional
from app.core.config import settings

EXPECTED_COLS = 5
DECIMAL_COLS  = {3, 4}  # LIST PRICE dan CURRENT PRICE


def validate_price_file(filepath: Path) -> dict:
    errors = []
    raw = filepath.read_bytes()

    # 1. Trailing newline
    if not raw.endswith(b"\n"):
        errors.append({
            "row": None, "column": None,
            "message": "File tidak diakhiri dengan 1 baris kosong (enter) di bagian paling bawah."
        })
    elif raw.endswith(b"\n\n"):
        errors.append({
            "row": None, "column": None,
            "message": "File memiliki lebih dari 1 baris kosong di bagian paling bawah."
        })

    text  = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    if not lines:
        return {
            "valid": False, "total_rows": 0,
            "errors": [{"row": None, "column": None, "message": "File kosong."}],
            "raw_lines": []
        }

    # 2. Baca header untuk label kolom saja — TIDAK divalidasi
    header_line = lines[0]
    if "\t" in header_line:
        header_cols = [h.strip() for h in header_line.split("\t")]
    else:
        header_cols = [h.strip() for h in re.split(r'  +', header_line) if h.strip()]

    # Pastikan header_cols punya cukup elemen
    while len(header_cols) < EXPECTED_COLS:
        header_cols.append(f"Kolom {len(header_cols) + 1}")

    # 3. Validasi isi — mulai dari baris ke-2
    data_lines = lines[1:]

    for line_idx, line in enumerate(data_lines):
        row_num = line_idx + 2

        # Baris kosong
        if line.strip() == "":
            if line_idx < len(data_lines) - 1:
                errors.append({
                    "row": row_num, "column": None,
                    "message": "Baris kosong ditemukan di tengah file."
                })
            continue

        # Cek tab separator
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

        # Cek jumlah kolom harus tepat 5
        if len(cols) != EXPECTED_COLS:
            found_vals = " | ".join(f"'{c}'" for c in cols[:6])
            errors.append({
                "row": row_num, "column": None,
                "message": (
                    f"Jumlah kolom tidak sesuai pada baris {row_num}. "
                    f"Ditemukan {len(cols)} kolom, seharusnya {EXPECTED_COLS}. "
                    f"Nilai ditemukan: {found_vals}. "
                    f"Kemungkinan: ada kolom yang hilang atau pemisah bukan Tab."
                )
            })
            continue

        # Cek semua 5 kolom wajib tidak boleh kosong
        for idx in range(EXPECTED_COLS):
            col_label = header_cols[idx]
            val_clean = cols[idx].strip()
            if not val_clean:
                errors.append({
                    "row": row_num, "column": col_label,
                    "message": f"Kolom '{col_label}' tidak boleh kosong pada baris {row_num}."
                })

        # Cek spasi tersembunyi di semua kolom
        for idx, val in enumerate(cols):
            col_label = header_cols[idx]
            if val != val.rstrip():
                errors.append({
                    "row": row_num, "column": col_label,
                    "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"
                })
            if val != val.lstrip():
                errors.append({
                    "row": row_num, "column": col_label,
                    "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"
                })

        # Cek format desimal LIST PRICE (index 3) dan CURRENT PRICE (index 4)
        for idx in DECIMAL_COLS:
            if idx < len(cols):
                col_label = header_cols[idx]
                v = cols[idx].strip()
                if not v:
                    continue  # Sudah ditangkap cek kolom kosong
                if "," in v:
                    errors.append({
                        "row": row_num, "column": col_label,
                        "message": (
                            f"{col_label} menggunakan koma sebagai desimal, "
                            f"seharusnya titik. Nilai: '{v}'"
                        )
                    })
                else:
                    try:
                        float(v)
                    except ValueError:
                        errors.append({
                            "row": row_num, "column": col_label,
                            "message": f"{col_label} bukan angka valid. Nilai: '{v}'"
                        })

    return {
        "valid": len(errors) == 0,
        "total_rows": len(data_lines),
        "errors": errors,
        "raw_lines": lines,
    }


def run_price_validation(folder: str, filename: Optional[str] = None) -> list:
    base = settings.INBOX_DIR if folder == "inbox" else settings.ERROR_DIR
    results = []
    if filename:
        fp = base / filename
        if not fp.exists():
            return [{"file": filename, "valid": False, "total_rows": 0, "folder": folder,
                     "errors": [{"row": None, "column": None,
                                 "message": f"File '{filename}' tidak ditemukan di folder {folder}."}]}]
        result = validate_price_file(fp)
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
            result = validate_price_file(fp)
            result["file"] = fp.name
            result["folder"] = folder
            results.append(result)
    return results
