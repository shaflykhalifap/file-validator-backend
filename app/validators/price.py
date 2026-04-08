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

# ── Helper: analisis perbedaan header per kolom ──────────────

def _normalize_spaces(s: str) -> str:
    import re as _re
    return _re.sub(r' +', ' ', s.strip())


def _analyze_header_errors(found: list[str], expected: list[str], row: int) -> list[dict]:
    """
    Bandingkan header kolom per kolom — deteksi nama salah, spasi berlebih/kurang, dll.
    """
    errors = []

    if len(found) != len(expected):
        errors.append({
            "row": row, "column": None,
            "message": (
                f"Jumlah kolom header tidak sesuai. "
                f"Ditemukan {len(found)} kolom, seharusnya {len(expected)} kolom. "
                f"Kemungkinan penyebab: ada kolom yang hilang, atau pemisah header bukan Tab."
            )
        })
        check_count = min(len(found), len(expected))
    else:
        check_count = len(expected)

    for i in range(check_count):
        f = found[i]
        e = expected[i]
        f_stripped = f.strip()

        if f_stripped == e:
            if f != f_stripped:
                errors.append({
                    "row": row, "column": f"Kolom {i+1}",
                    "message": f"Header kolom {i+1} (\'{e}\') mengandung spasi di awal atau akhir."
                })
        else:
            f_norm = _normalize_spaces(f_stripped)
            e_norm = _normalize_spaces(e)

            if f_norm == e_norm:
                # Nama sama setelah normalisasi → masalah jumlah spasi dalam nama
                errors.append({
                    "row": row, "column": f"Kolom {i+1}",
                    "message": (
                        f"Nama header kolom {i+1} memiliki spasi yang tidak tepat. "
                        f"Ditemukan: \'{f_stripped}\' | Seharusnya: \'{e}\' "
                        f"(periksa jumlah spasi antar kata, termasuk di sekitar karakter \'/')"
                    )
                })
            else:
                errors.append({
                    "row": row, "column": f"Kolom {i+1}",
                    "message": f"Nama header kolom {i+1} salah. Ditemukan: \'{f_stripped}\' | Seharusnya: \'{e}\'"
                })

    return errors


def validate_price_file(filepath: Path) -> dict:
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

    # 2. Validasi header — TIDAK berhenti meski header salah
    header_line = lines[0]

    # Deteksi apakah header pakai tab atau tidak
    if "\t" not in header_line and len(PRICE_HEADERS) > 1:
        errors.append({"row": 1, "column": None,
                        "message": "Pemisah antar kolom pada baris header bukan Tab. Pastikan menggunakan karakter Tab (bukan spasi) untuk memisahkan kolom."})
        # Coba split dengan spasi sebagai fallback untuk tetap validasi isi
        headers = [h.strip() for h in header_line.split("  ") if h.strip()]
    else:
        headers = header_line.split("\t")

    headers_stripped = [h.strip() for h in headers]

    if headers_stripped != PRICE_HEADERS:
        header_errors = _analyze_header_errors(headers, PRICE_HEADERS, 1)
        errors.extend(header_errors)
        header_valid = False
    else:
        header_valid = True
        # Cek trailing space di header yang benar
        for i, h in enumerate(headers):
            if h != h.strip():
                errors.append({"row": 1, "column": PRICE_HEADERS[i],
                                "message": f"Header kolom '{PRICE_HEADERS[i]}' mengandung spasi di awal atau akhir."})

    # 3. Validasi isi — SELALU dijalankan meskipun header salah
    data_lines = lines[1:]
    for line_idx, line in enumerate(data_lines):
        row_num = line_idx + 2

        if line == "":
            if line_idx < len(data_lines) - 1:
                errors.append({"row": row_num, "column": None,
                                "message": "Baris kosong ditemukan di tengah file."})
            continue

        # Deteksi pemisah
        if "\t" not in line:
            errors.append({"row": row_num, "column": None,
                            "message": (
                                f"Baris {row_num} tidak menggunakan Tab sebagai pemisah kolom. "
                                f"Periksa pemisah antara setiap nilai pada baris ini."
                            )})
            continue

        cols = line.split("\t")

        if len(cols) != 5:
            # Beri konteks mengapa jumlah kolom salah
            found_vals = " | ".join(f"'{c}'" for c in cols[:6])
            errors.append({
                "row": row_num, "column": None,
                "message": (
                    f"Jumlah kolom tidak sesuai pada baris {row_num}. "
                    f"Ditemukan {len(cols)} kolom, seharusnya 5. "
                    f"Nilai yang ditemukan: {found_vals}. "
                    f"Kemungkinan: ada kolom yang hilang atau pemisah bukan Tab."
                )
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

        for col_name, val in col_map.items():
            if val != val.rstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di akhir cell. Nilai: '{val}'"})
            if val != val.lstrip():
                errors.append({"row": row_num, "column": col_name,
                                "message": f"Terdapat spasi di awal cell. Nilai: '{val}'"})

        legal_clean = legal.strip()
        if not (legal_clean.isdigit() and len(legal_clean) == 4):
            errors.append({"row": row_num, "column": "LEGAL ENTITY CODE",
                            "message": f"LEGAL ENTITY CODE harus tepat 4 digit angka. Nilai: '{legal_clean}'"})

        for col_name, val_raw in [("LIST PRICE", list_price), ("CURRENT PRICE", curr_price)]:
            v = val_raw.strip()
            if "," in v:
                errors.append({"row": row_num, "column": col_name,
                                "message": f"{col_name} menggunakan koma sebagai desimal, seharusnya titik. Nilai: '{v}'"})
            else:
                try:
                    float(v)
                except ValueError:
                    errors.append({"row": row_num, "column": col_name,
                                    "message": f"{col_name} bukan angka valid. Nilai: '{v}'"})

    return {"valid": len(errors) == 0, "total_rows": len(data_lines), "errors": errors}


def run_price_validation(folder: str, filename: Optional[str] = None) -> list[dict]:
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
