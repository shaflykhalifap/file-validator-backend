"""
Authentication module.
- Verifikasi user dari tabel `user` di MySQL
- Generate & validasi JWT token
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from werkzeug.security import check_password_hash, generate_password_hash
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Password helpers ──────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    # Support plain text sementara (untuk migrasi) dan werkzeug hash
    if hashed.startswith("scrypt:") or hashed.startswith("pbkdf2:"):
        return check_password_hash(hashed, plain)
    # Fallback plain text (hapus setelah semua password di-hash)
    return plain == hashed


# ── DB user lookup ────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[dict]:
    """
    Cari user di tabel `user` berdasarkan email.
    Return dict user atau None jika tidak ditemukan / nonaktif.
    """
    try:
        # Import di sini untuk hindari circular import
        from app.core.database import get_connection
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # Ambil semua kolom — biarkan DB yang tentukan kolom apa yang ada
        cursor.execute(
            "SELECT * FROM user WHERE email = %s LIMIT 1",
            (email,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            return None

        # Cek is_active jika kolom ada
        if "is_active" in user and not user["is_active"]:
            return None

        # Normalisasi — pastikan key yang dibutuhkan selalu ada
        user.setdefault("username", user.get("email", ""))
        user.setdefault("role", "user")
        user.setdefault("name", user.get("email", "unknown"))

        return user
    except Exception as e:
        print(f"[AUTH ERROR] Gagal query user: {e}")
        return None


def update_last_login(email: str):
    """Update kolom last_login setelah user berhasil login (jika kolom ada)."""
    try:
        from app.core.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user SET last_login = %s WHERE email = %s",
            (datetime.now(), email)
        )
        cursor.close()
        conn.close()
    except Exception as e:
        # Kolom last_login mungkin belum ada — tidak perlu crash
        print(f"[AUTH WARNING] Gagal update last_login (kolom mungkin belum ada): {e}")


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Verifikasi email + password.
    Return dict user jika valid, None jika gagal.
    """
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


# ── JWT ──────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency FastAPI — validasi JWT token dari header Authorization.
    Dipakai di semua endpoint yang butuh autentikasi.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah expired. Silakan login kembali.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user
