from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import settings

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
http_bearer = HTTPBearer()


class TokenData(BaseModel):
    user_id: int
    email: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> TokenData:
    """Vérifie le JWT — à injecter avec Depends() dans les endpoints protégés."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        email   = payload.get("email")
        role    = payload.get("role", "user")
        if user_id is None or email is None:
            raise exc
        return TokenData(user_id=int(user_id), email=email, role=role)
    except JWTError:
        raise exc


def require_role(*roles: str):
    """Restreint un endpoint à certains rôles.

    Exemple :
        @router.get("/dashboard/heatmap")
        def heatmap(user = Depends(require_role("admin", "analyste"))):
    """
    def _check(
        credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    ) -> TokenData:
        user = get_current_user(credentials)
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès réservé aux rôles : {', '.join(roles)}",
            )
        return user
    return _check