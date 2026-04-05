"""
Fetch file dari mdbgo.io via HTTP.
Struktur URL: /price/inbox/file.txt, /inventory/error/file.txt, dst.
"""
import urllib.request
import urllib.error
import tempfile
import json
from pathlib import Path
from app.core.config import settings

# Map file_type ke nama folder di server
FOLDER_MAP = {
    "price":     "price",
    "inventory": "inventory",
    "master":    "master_product",
}


def fetch_remote_file(filename: str, file_type: str, folder: str) -> Path:
    """
    Download file dari mdbgo.io ke temporary file lokal.
    URL format: /price/inbox/namafile.txt
    """
    from fastapi import HTTPException

    type_folder = FOLDER_MAP.get(file_type, file_type)
    url = f"{settings.REMOTE_BASE_URL}/{type_folder}/{folder}/{filename}"

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=404,
            detail=f"File '{filename}' tidak ditemukan di {type_folder}/{folder}. ({e.code})")
    except urllib.error.URLError as e:
        raise HTTPException(status_code=503,
            detail=f"Tidak bisa akses server file. ({e.reason})")


def list_remote_files(file_type: str, folder: str) -> list[dict]:
    """
    Ambil daftar file dari PHP API di mdbgo.io.
    """
    from fastapi import HTTPException

    type_folder = FOLDER_MAP.get(file_type, file_type)
    url = f"{settings.REMOTE_BASE_URL}/api/list-files.php?type={type_folder}&folder={folder}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        return data.get("files", [])
    except Exception as e:
        raise HTTPException(status_code=503,
            detail=f"Gagal ambil daftar file dari server: {str(e)}")
