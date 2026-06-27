from dataclasses import dataclass

from itsdangerous import URLSafeSerializer
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
SESSION_KEY = "tetra_host_session"


@dataclass(frozen=True)
class SessionUser:
    user_id: int
    tenant_id: int
    email: str
    role: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().app_secret, salt=SESSION_KEY)


def create_session_token(user: SessionUser) -> str:
    return _serializer().dumps(
        {
            "user_id": user.user_id,
            "tenant_id": user.tenant_id,
            "email": user.email,
            "role": user.role,
        }
    )


def parse_session_token(token: str) -> SessionUser | None:
    try:
        payload = _serializer().loads(token)
    except Exception:
        return None
    return SessionUser(
        user_id=int(payload["user_id"]),
        tenant_id=int(payload["tenant_id"]),
        email=str(payload["email"]),
        role=str(payload["role"]),
    )
