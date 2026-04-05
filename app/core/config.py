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

    # ── Folder paths ─────────────────────────────────────
    # Di server mdbgo.io, path absolut ke folder inbox & error
    # Sesuaikan dengan struktur folder di server Anda
    INBOX_DIR: Path = Path("/project_java/inbox")
    ERROR_DIR: Path = Path("/project_java/error")

    class Config:
        env_file = ".env"


settings = Settings()
