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


def _analyze_header_errors(found: list[str], expected: list[str], row: int) -> list[dict]:
    errors = []
    if len(found) != len(expected):
        errors.append({
            "row": row, "column": None,
            "message": (
                f"Jumlah kolom header tidak sesuai. "
                f"Ditemukan {len(found)} kolom, seharusnya {len(expected)} kolom. "
                f"Kemungkinan: ada kolom yang hilang, atau pemisah header bukan Tab."
            )
        })
    check_count = min(len(found), len(expected))
    for i in range(check_count):
        f = found[i]
        e = expected[i]
        f_stripped = f.strip()
        if f_stripped == e:
            if f != f_stripped:
                errors.append({"row": row, "column": f"Kolom {i+1} ({e})",
                                "message": f"Header kolom {i+1} ('{e}') mengandung spasi di awal atau akhir."})
        else:
            # Cek apakah masalah spasi di sekitar '/'
            if '/' in e:
                e_no_space = e.replace(' / ', '/').replace('/ ', '/').replace(' /', '/')
                f_no_space = f_stripped.replace(' / ', '/').replace('/ ', '/').replace(' /', '/')
                if f_no_space == e_no_space:
                    errors.append({
                        "row": row, "column": f"Kolom {i+1}",
                        "message": (
                            f"Header kolom {i+1} memiliki masalah spasi di sekitar karakter '/'. "
                            f"Ditemukan: '{f_stripped}' | Seharusnya: '{e}' "
                            f"(perhatikan tidak boleh ada spasi di sekitar '/' pada nama kolom ini)"
                        )
                    })
                    continue
            # Cek apakah seharusnya tidak ada '/' tapi ada spasi
            if '/' not in e and f_stripped.replace(' ', '') == e.replace(' ', ''):
                errors.append({
                    "row": row, "column": f"Kolom {i+1}",
                    "message": (
                        f"Header kolom {i+1} menggunakan spasi alih-alih Tab sebagai pemisah. "
                        f"Ditemukan: '{f_stripped}' | Seharusnya: '{e}'"
                    )
                })
                continue
            errors.append({
                "row": row, "column": f"Kolom {i+1}",
                "message": f"Nama header kolom {i+1} salah. Ditemukan: '{f_stripped}' | Seharusnya: '{e}'"
            })
    return errors


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

    # 2. Validasi header — TIDAK berhenti meski salah
    header_line = lines[0]

    if "\t" not in header_line and len(MASTER_HEADERS) > 1:
        errors.append({"row": 1, "column": None,
                        "message": "Pemisah antar kolom pada baris header bukan Tab."})
        headers = [h.strip() for h in header_line.split("  ") if h.strip()]
    else:
        headers = header_line.split("\t")

    headers_stripped = [h.strip() for h in headers]

    if headers_stripped != MASTER_HEADERS:
        header_errors = _analyze_header_errors(headers, MASTER_HEADERS, 1)
        errors.extend(header_errors)
    else:
        for i, h in enumerate(headers):
            if h != h.strip():
                errors.append({"row": 1, "column": MASTER_HEADERS[i],
                                "message": f"Header kolom '{MASTER_HEADERS[i]}' mengandung spasi di awal atau akhir."})

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
                    f"Periksa pemisah antara setiap nilai."
                )
            })
            continue

        cols = line.split("\t")

        # Fleksibel: terima 14, 15, atau 16 kolom
        # 14 = hanya kolom consumed (normal jika 2 terakhir dikosongkan tanpa tab)
        # 15 = kolom ke-15 ada isi (DISCONTINUATION terisi)
        # 16 = semua kolom ada (normal atau ke-15/16 ada isi)
        if len(cols) < 14:
            found_vals = " | ".join(f"'{c}'" for c in cols[:5])
            errors.append({
                "row": row_num, "column": None,
                "message": (
                    f"Jumlah kolom tidak sesuai pada baris {row_num}. "
                    f"Ditemukan {len(cols)} kolom, seharusnya minimal 14 kolom. "
                    f"5 nilai pertama: {found_vals}. "
                    f"Kemungkinan: ada kolom yang hilang atau pemisah bukan Tab."
                )
            })
            continue

        # Pad ke 16 kolom jika kurang (kolom kosong di akhir)
        while len(cols) < 16:
            cols.append("")

        # Cek kolom ke-15 dan ke-16 (DISCONTINUATION & CONCEPT) harus kosong
        disc_val = cols[14].strip()  # kolom 15 (index 14)
        conc_val = cols[15].strip()  # kolom 16 (index 15)

        if disc_val:
            errors.append({
                "row": row_num, "column": "DISCONTINUATION",
                "message": (
                    f"Kolom 'DISCONTINUATION' (kolom ke-15) seharusnya kosong karena tidak di-consume sistem. "
                    f"Ditemukan nilai: '{disc_val}'. Hapus isi kolom ini."
                )
            })

        if conc_val:
            errors.append({
                "row": row_num, "column": "CONCEPT",
                "message": (
                    f"Kolom 'CONCEPT' (kolom ke-16) seharusnya kosong karena tidak di-consume sistem. "
                    f"Ditemukan nilai: '{conc_val}'. Hapus isi kolom ini."
                )
            })

        col_map = {MASTER_HEADERS[i]: cols[i] for i in range(16)}

        # Cek trailing/leading spasi untuk 14 kolom consumed
        for col_name in MASTER_HEADERS[:CONSUMED_COLUMNS]:
            val = col_map[col_name]
            if val != val.rstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"})
            if val != val.lstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"})

        # Cek SKU mengandung SPU
        spu = col_map["PARENT/GENERIC/SPU"].strip()
        sku = col_map["ARTICLE NUMBER/VARIANT/SKU"].strip()
        if spu and sku and spu not in sku:
            errors.append({"row": row_num, "column": "ARTICLE NUMBER/VARIANT/SKU",
                            "message": (
                                f"Nilai SKU harus mengandung nilai SPU. "
                                f"SPU: '{spu}' | SKU: '{sku}' — '{spu}' tidak ditemukan di dalam '{sku}'"
                            )})

        # Cek UPC == MAIN UPC
        upc = col_map["UPC"].strip()
        main_upc = col_map["MAIN UPC"].strip()
        if upc != main_upc:
            errors.append({"row": row_num, "column": "MAIN UPC",
                            "message": (
                                f"Nilai UPC dan MAIN UPC harus identik. "
                                f"UPC: '{upc}' | MAIN UPC: '{main_upc}'"
                            )})

        # Cek LEGAL ENTITY CODE
        legal = col_map["LEGAL ENTITY CODE"].strip()
        if not (legal.isdigit() and len(legal) == 4):
            errors.append({"row": row_num, "column": "LEGAL ENTITY CODE",
                            "message": f"LEGAL ENTITY CODE harus tepat 4 digit angka. Nilai: '{legal}'"})

        # Cek UPC tidak kosong
        if not upc:
            errors.append({"row": row_num, "column": "UPC",
                            "message": "Kolom UPC tidak boleh kosong."})

        # Cek kolom wajib tidak kosong (12 kolom pertama)
        required_cols = MASTER_HEADERS[:12]
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
        for fp in sorted(files):
            result = validate_master_file(fp)
            result["file"] = fp.name
            result["folder"] = folder
            results.append(result)
    return results
