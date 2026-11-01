from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from sqlalchemy.orm import Session

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)
from app.db.database import get_db
from app.db.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
        ),
    }
    return jwt.encode(
        {"alg": JWT_ALGORITHM, "typ": "JWT"},
        claims,
        OctKey.import_key(JWT_SECRET_KEY),
        algorithms=[JWT_ALGORITHM],
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        token = jwt.decode(
            credentials.credentials,
            OctKey.import_key(JWT_SECRET_KEY),
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(token.claims["sub"])
        if int(token.claims["exp"]) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
    except (JoseError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
