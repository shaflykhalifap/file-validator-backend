from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from app.core.auth import authenticate_user, create_access_token, get_current_user, update_last_login

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah.",
        )
    update_last_login(user["email"])
    token = create_access_token({"sub": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id":       user.get("id", 0),
            "name":     user.get("name", user.get("email", "")),
            "email":    user.get("email", ""),
            "username": user.get("username", user.get("email", "")),
            "role":     user.get("role", "user"),
        },
    }


@router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return {
        "id":       current_user.get("id", 0),
        "name":     current_user.get("name", current_user.get("email", "")),
        "email":    current_user.get("email", ""),
        "username": current_user.get("username", current_user.get("email", "")),
        "role":     current_user.get("role", "user"),
    }
