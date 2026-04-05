from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
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


class ValidateRequest(BaseModel):
    filename: Optional[str] = None


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


def _save_to_db(results: list[dict], file_type: str, validated_by: str, source: str):
    for r in results:
        if r.get("file") is None:
            continue
        try:
            save_validation_result(
                filename=r["file"],
                file_type=file_type,
                source=source,
                validated_by=validated_by,
                status="valid" if r["valid"] else "invalid",
                total_rows=r.get("total_rows", 0),
                total_errors=len(r.get("errors", [])),
                error_details=r.get("errors", []),
                notes=f"Validasi via {'web' if '@' in validated_by else 'API Postman'}",
            )
        except Exception as e:
            print(f"[DB WARNING] Gagal simpan log untuk {r['file']}: {e}")


@router.post("/inbox/price")
async def validate_inbox_price(body: ValidateRequest, user=Depends(get_current_user)):
    results = run_price_validation("inbox", body.filename)
    _save_to_db(results, "price", user["email"], "inbox")
    return _build_response(results)

@router.post("/error/price")
async def validate_error_price(body: ValidateRequest, user=Depends(get_current_user)):
    results = run_price_validation("error", body.filename)
    _save_to_db(results, "price", user["email"], "error")
    return _build_response(results)

@router.post("/inbox/inventory")
async def validate_inbox_inventory(body: ValidateRequest, user=Depends(get_current_user)):
    results = run_inventory_validation("inbox", body.filename)
    _save_to_db(results, "inventory", user["email"], "inbox")
    return _build_response(results)

@router.post("/error/inventory")
async def validate_error_inventory(body: ValidateRequest, user=Depends(get_current_user)):
    results = run_inventory_validation("error", body.filename)
    _save_to_db(results, "inventory", user["email"], "error")
    return _build_response(results)

@router.post("/inbox/master-product")
async def validate_inbox_master(body: ValidateRequest, user=Depends(get_current_user)):
    results = run_master_validation("inbox", body.filename)
    _save_to_db(results, "master", user["email"], "inbox")
    return _build_response(results)

@router.post("/error/master-product")
async def validate_error_master(body: ValidateRequest, user=Depends(get_current_user)):
    results = run_master_validation("error", body.filename)
    _save_to_db(results, "master", user["email"], "error")
    return _build_response(results)

@router.post("/upload/price")
async def upload_price(file: UploadFile = File(...), user=Depends(get_current_user)):
    result = await _handle_upload(file, validate_price_file)
    _save_to_db(result["results"], "price", user["email"], "upload")
    return result

@router.post("/upload/inventory")
async def upload_inventory(file: UploadFile = File(...), user=Depends(get_current_user)):
    result = await _handle_upload(file, validate_inventory_file)
    _save_to_db(result["results"], "inventory", user["email"], "upload")
    return result

@router.post("/upload/master-product")
async def upload_master(file: UploadFile = File(...), user=Depends(get_current_user)):
    result = await _handle_upload(file, validate_master_file)
    _save_to_db(result["results"], "master", user["email"], "upload")
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

@router.get("/logs")
async def get_logs(
    file_type: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    _=Depends(get_current_user),
):
    try:
        logs = get_validation_logs(file_type, source, status, limit, offset)
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil log: {str(e)}")

@router.get("/summary")
async def get_summary(_=Depends(get_current_user)):
    try:
        return get_validation_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil summary: {str(e)}")


# ══════════════════════════════════════════════════════════════
#  LIST FILES — tampilkan file yang ada di folder
# ══════════════════════════════════════════════════════════════
@router.get("/files/{folder}")
async def list_files(folder: str, _=Depends(get_current_user)):
    """
    Ambil daftar file .txt yang ada di folder inbox atau error.
    folder: 'inbox' atau 'error'
    """
    if folder not in ("inbox", "error"):
        raise HTTPException(status_code=400, detail="Folder harus 'inbox' atau 'error'.")

    base = settings.INBOX_DIR if folder == "inbox" else settings.ERROR_DIR

    if not base.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Folder '{folder}' tidak ditemukan di path: {base}"
        )

    files = sorted(base.glob("*.txt"))
    result = []
    for f in files:
        stat = f.stat()
        result.append({
            "filename": f.name,
            "size_kb": round(stat.st_size / 1024, 1),
            "modified": stat.st_mtime,
        })

    return {"folder": folder, "path": str(base), "files": result, "count": len(result)}
