from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # ── JWT ──────────────────────────────────────────────
    SECRET_KEY: str = "changeme-use-strong-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 jam

    # ── Database MySQL (mdbgo.com) ────────────────────────
    DB_HOST: str = "mysql.db.mdbgo.com"
    DB_USER: str = "sufelin_sufelin"
    DB_PASS: str = "Sufelin76*"
    DB_NAME: str = "sufelin_dbkampus"

    # ── URL server mdbgo.io (untuk fetch file via HTTP) ───
    REMOTE_BASE_URL: str = "http://project_java.mdbgo.io"

    # ── Folder paths (hanya dipakai jika LOCAL_MODE=true) ─
    # Isi ini jika FastAPI dan folder inbox/error ada di server yang sama
    INBOX_DIR: Path = Path("/home/sufelin/public_html/project_java/inbox")
    ERROR_DIR: Path = Path("/home/sufelin/public_html/project_java/error")

    # ── Mode: local = baca file langsung, remote = fetch via HTTP ──
    # Di Railway otomatis jadi remote karena folder tidak ada
    @property
    def is_local_mode(self) -> bool:
        return self.INBOX_DIR.exists()

    class Config:
        env_file = ".env"


settings = Settings()
