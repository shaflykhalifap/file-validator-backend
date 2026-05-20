"""
Master Product File Validator
- Tidak memvalidasi header
- Minimal 14 kolom per baris, padding otomatis ke 16 jika kurang
- Kolom 15 (DISCONTINUATION) dan 16 (CONCEPT) harus kosong
- Legal Entity Code tidak divalidasi formatnya
- Kolom PARENT/GENERIC/SPU, YEAR, SEASON boleh kosong
- SKU harus mengandung SPU (jika SPU tidak kosong)
- UPC harus identik dengan MAIN UPC
"""
from pathlib import Path
from typing import Optional
from app.core.config import settings

MASTER_HEADERS = [
    "UPC",                          # 0  — wajib diisi
    "PARENT/GENERIC/SPU",           # 1  — boleh kosong
    "ARTICLE NUMBER/VARIANT/SKU",   # 2  — wajib diisi
    "BRAND CODE",                   # 3  — wajib diisi
    "BRAND NAME",                   # 4  — wajib diisi
    "PRODUCT NAME",                 # 5  — wajib diisi
    "COLOR",                        # 6  — wajib diisi
    "SIZE1",                        # 7  — wajib diisi
    "YEAR",                         # 8  — boleh kosong
    "SEASON",                       # 9  — boleh kosong
    "CATEGORY",                     # 10 — wajib diisi
    "SBU CODE",                     # 11 — wajib diisi
    "LEGAL ENTITY CODE",            # 12 — wajib diisi, bebas format
    "MAIN UPC",                     # 13 — wajib diisi
    "DISCONTINUATION",              # 14 — wajib KOSONG
    "CONCEPT",                      # 15 — wajib KOSONG
]
CONSUMED_COLUMNS = 14
NULLABLE_COLS    = {"PARENT/GENERIC/SPU", "YEAR", "SEASON"}


def validate_master_file(filepath: Path) -> dict:
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

    content = raw.decode("utf-8", errors="replace")
    lines   = content.splitlines()

    if not lines:
        return {
            "valid": False, "total_rows": 0,
            "errors": [{"row": None, "column": None, "message": "File kosong."}],
            "raw_lines": []
        }

    # 2. Header tidak divalidasi — langsung ke isi mulai baris ke-2
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
                    f"Periksa pemisah antara setiap nilai."
                )
            })
            continue

        cols = line.split("\t")

        # Cek jumlah kolom minimal 14
        if len(cols) < CONSUMED_COLUMNS:
            found_vals = " | ".join(f"'{c}'" for c in cols[:5])
            errors.append({
                "row": row_num, "column": None,
                "message": (
                    f"Jumlah kolom tidak sesuai pada baris {row_num}. "
                    f"Ditemukan {len(cols)} kolom, seharusnya minimal {CONSUMED_COLUMNS}. "
                    f"5 nilai pertama: {found_vals}. "
                    f"Kemungkinan: ada kolom yang hilang atau pemisah bukan Tab."
                )
            })
            continue

        # Padding otomatis ke 16 kolom jika kurang
        # (kolom 15 & 16 boleh tidak ada tab-nya, dianggap kosong)
        while len(cols) < 16:
            cols.append("")

        # Cek kolom 15 & 16 harus kosong
        if cols[14].strip():
            errors.append({
                "row": row_num, "column": "DISCONTINUATION",
                "message": (
                    f"Kolom 'DISCONTINUATION' (kolom ke-15) harus kosong. "
                    f"Ditemukan: '{cols[14].strip()}'. Hapus isi kolom ini."
                )
            })
        if cols[15].strip():
            errors.append({
                "row": row_num, "column": "CONCEPT",
                "message": (
                    f"Kolom 'CONCEPT' (kolom ke-16) harus kosong. "
                    f"Ditemukan: '{cols[15].strip()}'. Hapus isi kolom ini."
                )
            })

        col_map = {MASTER_HEADERS[i]: cols[i] for i in range(16)}

        # Cek spasi tersembunyi untuk 14 kolom consumed
        for col_name in MASTER_HEADERS[:CONSUMED_COLUMNS]:
            val = col_map[col_name]
            if val != val.rstrip():
                errors.append({
                    "row": row_num, "column": col_name,
                    "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"
                })
            if val != val.lstrip():
                errors.append({
                    "row": row_num, "column": col_name,
                    "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"
                })

        # Cek kolom wajib tidak boleh kosong
        for col_name in MASTER_HEADERS[:CONSUMED_COLUMNS]:
            if col_name not in NULLABLE_COLS:
                if not col_map[col_name].strip():
                    errors.append({
                        "row": row_num, "column": col_name,
                        "message": f"Kolom '{col_name}' tidak boleh kosong pada baris {row_num}."
                    })

        # Cek SKU harus mengandung SPU (hanya jika SPU tidak kosong)
        spu = col_map["PARENT/GENERIC/SPU"].strip()
        sku = col_map["ARTICLE NUMBER/VARIANT/SKU"].strip()
        if spu and sku and spu not in sku:
            errors.append({
                "row": row_num, "column": "ARTICLE NUMBER/VARIANT/SKU",
                "message": (
                    f"Nilai SKU harus mengandung nilai SPU. "
                    f"SPU: '{spu}' | SKU: '{sku}' — "
                    f"'{spu}' tidak ditemukan di dalam '{sku}'"
                )
            })

        # Cek UPC harus identik dengan MAIN UPC
        upc      = col_map["UPC"].strip()
        main_upc = col_map["MAIN UPC"].strip()
        if upc and main_upc and upc != main_upc:
            errors.append({
                "row": row_num, "column": "MAIN UPC",
                "message": (
                    f"Nilai UPC dan MAIN UPC harus identik. "
                    f"UPC: '{upc}' | MAIN UPC: '{main_upc}'"
                )
            })

    return {
        "valid": len(errors) == 0,
        "total_rows": len(data_lines),
        "errors": errors,
        "raw_lines": lines,
    }


def run_master_validation(folder: str, filename: Optional[str] = None) -> list:
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
