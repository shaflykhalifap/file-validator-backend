"""
Utility untuk fetch file dari server mdbgo.io via HTTP.
Dipakai saat FastAPI berjalan di cloud (Railway) dan
folder inbox/error ada di server mdbgo.io.
"""
import urllib.request
import urllib.error
import tempfile
from pathlib import Path
from app.core.config import settings


def fetch_remote_file(filename: str, folder: str) -> Path:
    """
    Download file dari mdbgo.io ke temporary file lokal.
    Return path temporary file (harus di-delete setelah dipakai).
    Raise HTTPException jika file tidak ditemukan.
    """
    from fastapi import HTTPException

    url = f"{settings.REMOTE_BASE_URL}/{folder}/{filename}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()

        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    except urllib.error.HTTPError as e:
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' tidak ditemukan di folder {folder}. ({e.code})"
        )
    except urllib.error.URLError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Tidak bisa mengakses server file. Pastikan server mdbgo.io online. ({e.reason})"
        )


def list_remote_files(folder: str) -> list[dict]:
    """
    Ambil daftar file .txt dari folder inbox/error di mdbgo.io.
    Memanfaatkan endpoint /api/list-files.php yang akan kita buat di server.
    """
    from fastapi import HTTPException
    import json

    url = f"{settings.REMOTE_BASE_URL}/api/list-files.php?folder={folder}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        return data.get("files", [])
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Gagal mengambil daftar file dari server: {str(e)}"
        )
