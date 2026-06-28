from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings
from app.models import AdminUser

API_TOKEN_SALT = "tetra-host-api-token"


def get_api_token_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.app_secret, salt=API_TOKEN_SALT)


def create_api_token(settings: Settings, admin: AdminUser) -> str:
    serializer = get_api_token_serializer(settings)
    return serializer.dumps(
        {
            "admin_user_id": admin.id,
            "email": admin.email,
            "name": admin.full_name,
            "tenant_id": admin.tenant_id,
            "tenant_slug": admin.tenant.slug if admin.tenant else "",
        }
    )


def read_api_token(settings: Settings, token: str, *, max_age_seconds: int) -> dict[str, str] | None:
    serializer = get_api_token_serializer(settings)
    try:
        payload = serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    return payload if isinstance(payload, dict) else None
