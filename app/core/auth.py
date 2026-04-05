from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from werkzeug.security import check_password_hash
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("scrypt:") or hashed.startswith("pbkdf2:"):
        return check_password_hash(hashed, plain)
    return plain == hashed  # fallback plain text


def get_user_by_email(email: str) -> Optional[dict]:
    try:
        from app.core.database import get_connection
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user WHERE email = %s LIMIT 1", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user:
            return None
        if "is_active" in user and not user["is_active"]:
            return None
        user.setdefault("username", user.get("email", ""))
        user.setdefault("role", "user")
        user.setdefault("name", user.get("email", "unknown"))
        return user
    except Exception as e:
        print(f"[AUTH ERROR] Gagal query user: {e}")
        return None


def update_last_login(email: str):
    try:
        from app.core.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE user SET last_login = %s WHERE email = %s", (datetime.now(), email))
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[AUTH WARNING] Gagal update last_login: {e}")


def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah expired. Silakan login kembali.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user
