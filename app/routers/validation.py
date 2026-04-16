from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from typing import Optional
import tempfile
from pathlib import Path

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import save_validation_result, get_validation_logs, get_validation_summary
from app.validators.price import run_price_validation, validate_price_file
from app.validators.inventory import run_inventory_validation, validate_inventory_file
from app.validators.master import run_master_validation, validate_master_file

router = APIRouter(prefix="/validate", tags=["Validation"])


# ── Helpers ───────────────────────────────────────────────────

def _build_response(results: list[dict]) -> dict:
    total_files = len(results)
    valid_files = sum(1 for r in results if r["valid"])
    total_errors = sum(len(r["errors"]) for r in results)
    return {
        "summary": {
            "total_files": total_files,
            "valid_files": valid_files,
            "invalid_files": total_files - valid_files,
            "total_errors": total_errors,
        },
        "results": results,
    }


def _save_to_db(results, file_type, validated_by, source, via="web"):
    for r in results:
        if r.get("file") is None:
            continue
        try:
            save_validation_result(
                filename=r["file"], file_type=file_type, source=source,
                validated_by=validated_by,
                status="valid" if r["valid"] else "invalid",
                total_rows=r.get("total_rows", 0),
                total_errors=len(r.get("errors", [])),
                error_details=r.get("errors", []),
                notes=f"Validasi via {via}",
                raw_lines=r.get("raw_lines"),   # simpan raw_lines ke DB
            )
        except Exception as e:
            print(f"[DB WARNING] {e}")





async def _run_smart(file_type: str, folder: str, filename: Optional[str]) -> list[dict]:
    """
    Auto-detect local vs remote.
    file_type: 'price' | 'inventory' | 'master'
    folder   : 'inbox' | 'error'
    """
    validator_map = {
        "price":     (validate_price_file,     run_price_validation),
        "inventory": (validate_inventory_file,  run_inventory_validation),
        "master":    (validate_master_file,     run_master_validation),
    }
    validator_fn, run_fn = validator_map[file_type]

    # ── Local mode ──
    if settings.is_local_mode:
        base = settings.get_dir(file_type, folder)
        if filename:
            fp = base / filename
            if not fp.exists():
                return [{"file": filename, "folder": folder, "valid": False, "total_rows": 0,
                         "errors": [{"row": None, "column": None,
                                     "message": f"File '{filename}' tidak ditemukan."}]}]
            result = validator_fn(fp)
            result["file"] = filename
            result["folder"] = folder
            return [result]
        else:
            files = list(base.glob("*.txt"))
            if not files:
                return [{"file": None, "folder": folder, "valid": True, "total_rows": 0,
                         "errors": [{"row": None, "column": None,
                                     "message": f"Tidak ada file .txt di {file_type}/{folder}."}]}]
            results = []
            for fp in sorted(files):
                r = validator_fn(fp)
                r["file"] = fp.name
                r["folder"] = folder
                results.append(r)
            return results

    # ── Remote mode ──
    from app.core.remote_files import fetch_remote_file, list_remote_files

    if filename:
        filenames = [filename]
    else:
        filenames = [f["filename"] for f in list_remote_files(file_type, folder)]

    if not filenames:
        return [{"file": None, "folder": folder, "valid": True, "total_rows": 0,
                 "errors": [{"row": None, "column": None,
                             "message": f"Tidak ada file .txt di {file_type}/{folder}."}]}]

    results = []
    for fname in filenames:
        tmp_path = fetch_remote_file(fname, file_type, folder)
        try:
            result = validator_fn(tmp_path)
            result["file"] = fname
            result["folder"] = folder
            results.append(result)
        finally:
            tmp_path.unlink(missing_ok=True)
    return results


# ══════════════════════════════════════════════════════════════
#  PRICE
# ══════════════════════════════════════════════════════════════
@router.post("/inbox/price")
async def validate_inbox_price(filename: Optional[str] = Form(None), user=Depends(get_current_user)):
    results = await _run_smart("price", "inbox", filename or None)
    _save_to_db(results, "price", user["email"], "inbox", via="Postman / API")
    return _build_response(results)

@router.post("/error/price")
async def validate_error_price(filename: Optional[str] = Form(None), user=Depends(get_current_user)):
    results = await _run_smart("price", "error", filename or None)
    _save_to_db(results, "price", user["email"], "error", via="Postman / API")
    return _build_response(results)


# ══════════════════════════════════════════════════════════════
#  INVENTORY
# ══════════════════════════════════════════════════════════════
@router.post("/inbox/inventory")
async def validate_inbox_inventory(filename: Optional[str] = Form(None), user=Depends(get_current_user)):
    results = await _run_smart("inventory", "inbox", filename or None)
    _save_to_db(results, "inventory", user["email"], "inbox", via="Postman / API")
    return _build_response(results)

@router.post("/error/inventory")
async def validate_error_inventory(filename: Optional[str] = Form(None), user=Depends(get_current_user)):
    results = await _run_smart("inventory", "error", filename or None)
    _save_to_db(results, "inventory", user["email"], "error", via="Postman / API")
    return _build_response(results)


# ══════════════════════════════════════════════════════════════
#  MASTER PRODUCT
# ══════════════════════════════════════════════════════════════
@router.post("/inbox/master-product")
async def validate_inbox_master(filename: Optional[str] = Form(None), user=Depends(get_current_user)):
    results = await _run_smart("master", "inbox", filename or None)
    _save_to_db(results, "master", user["email"], "inbox", via="Postman / API")
    return _build_response(results)

@router.post("/error/master-product")
async def validate_error_master(filename: Optional[str] = Form(None), user=Depends(get_current_user)):
    results = await _run_smart("master", "error", filename or None)
    _save_to_db(results, "master", user["email"], "error", via="Postman / API")
    return _build_response(results)


# ══════════════════════════════════════════════════════════════
#  UPLOAD & VALIDATE
# ══════════════════════════════════════════════════════════════
@router.post("/upload/price")
async def upload_price(file: UploadFile = File(...), user=Depends(get_current_user)):
    result = await _handle_upload(file, validate_price_file)
    _save_to_db(result["results"], "price", user["email"], "upload", via="Web Upload")
    return result

@router.post("/upload/inventory")
async def upload_inventory(file: UploadFile = File(...), user=Depends(get_current_user)):
    result = await _handle_upload(file, validate_inventory_file)
    _save_to_db(result["results"], "inventory", user["email"], "upload", via="Web Upload")
    return result

@router.post("/upload/master-product")
async def upload_master(file: UploadFile = File(...), user=Depends(get_current_user)):
    result = await _handle_upload(file, validate_master_file)
    _save_to_db(result["results"], "master", user["email"], "upload", via="Web Upload")
    return result

async def _handle_upload(file: UploadFile, validator_fn) -> dict:
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Hanya file .txt yang diperbolehkan.")
    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)
    try:
        result = validator_fn(tmp_path)
        result["file"] = file.filename
        result["folder"] = "upload"
        return _build_response([result])
    finally:
        tmp_path.unlink(missing_ok=True)


# ══════════════════════════════════════════════════════════════
#  LIST FILES
# ══════════════════════════════════════════════════════════════
@router.get("/files/{file_type}/{folder}")
async def list_files(file_type: str, folder: str, _=Depends(get_current_user)):
    if file_type not in ("price", "inventory", "master"):
        raise HTTPException(status_code=400, detail="file_type harus: price, inventory, atau master.")
    if folder not in ("inbox", "error"):
        raise HTTPException(status_code=400, detail="folder harus: inbox atau error.")

    if settings.is_local_mode:
        base = settings.get_dir(file_type, folder)
        files = sorted(base.glob("*.txt"))
        return {"folder": folder, "file_type": file_type,
                "files": [{"filename": f.name, "size_kb": round(f.stat().st_size/1024,1),
                           "modified": f.stat().st_mtime} for f in files],
                "count": len(files)}

    from app.core.remote_files import list_remote_files
    files = list_remote_files(file_type, folder)
    return {"folder": folder, "file_type": file_type, "files": files, "count": len(files)}


# ══════════════════════════════════════════════════════════════
#  LOGS & SUMMARY
# ══════════════════════════════════════════════════════════════
@router.get("/logs")
async def get_logs(
    file_type: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    _=Depends(get_current_user),
):
    """Ambil riwayat log validasi. Mengembalikan list kosong jika DB tidak tersedia."""
    try:
        logs = get_validation_logs(file_type, source, status, limit, offset)
        return {"logs": logs or [], "count": len(logs or [])}
    except Exception as e:
        print(f"[LOGS ERROR] {e}")
        # Kembalikan list kosong agar frontend tidak crash
        return {"logs": [], "count": 0, "warning": "Database tidak tersedia saat ini."}


@router.get("/summary")
async def get_summary(_=Depends(get_current_user)):
    try:
        result = get_validation_summary()
        return result or {"overall": {}, "by_type": [], "recent": []}
    except Exception as e:
        print(f"[SUMMARY ERROR] {e}")
        return {"overall": {}, "by_type": [], "recent": []}

