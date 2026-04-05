from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # ── JWT ──────────────────────────────────────────────
    SECRET_KEY: str = "changeme-use-strong-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ── Database MySQL ────────────────────────────────────
    DB_HOST: str = "mysql.db.mdbgo.com"
    DB_USER: str = "sufelin_sufelin"
    DB_PASS: str = "Sufelin76*"
    DB_NAME: str = "sufelin_dbkampus"
    DB_PORT: int = 3306

    # ── URL server mdbgo.io ───────────────────────────────
    REMOTE_BASE_URL: str = "http://project_java.mdbgo.io"

    # ── Folder paths per file type (local mode) ───────────
    PRICE_INBOX_DIR:     Path = Path("/home/sufelin/public_html/project_java/price/inbox")
    PRICE_ERROR_DIR:     Path = Path("/home/sufelin/public_html/project_java/price/error")
    INVENTORY_INBOX_DIR: Path = Path("/home/sufelin/public_html/project_java/inventory/inbox")
    INVENTORY_ERROR_DIR: Path = Path("/home/sufelin/public_html/project_java/inventory/error")
    MASTER_INBOX_DIR:    Path = Path("/home/sufelin/public_html/project_java/master_product/inbox")
    MASTER_ERROR_DIR:    Path = Path("/home/sufelin/public_html/project_java/master_product/error")

    @property
    def is_local_mode(self) -> bool:
        return self.PRICE_INBOX_DIR.exists()

    def get_dir(self, file_type: str, folder: str) -> Path:
        """Helper ambil path folder berdasarkan file_type dan folder."""
        mapping = {
            ("price",    "inbox"): self.PRICE_INBOX_DIR,
            ("price",    "error"): self.PRICE_ERROR_DIR,
            ("inventory","inbox"): self.INVENTORY_INBOX_DIR,
            ("inventory","error"): self.INVENTORY_ERROR_DIR,
            ("master",   "inbox"): self.MASTER_INBOX_DIR,
            ("master",   "error"): self.MASTER_ERROR_DIR,
        }
        return mapping.get((file_type, folder))

    class Config:
        env_file = ".env"


settings = Settings()
