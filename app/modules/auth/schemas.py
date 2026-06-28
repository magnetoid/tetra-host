from pydantic import BaseModel, ConfigDict, field_validator


class LoginFormData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str
    password: str
    csrf_token: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.split("@")[-1]:
            msg = "Enter a valid email address."
            raise ValueError(msg)
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            msg = "Password must be at least 8 characters long."
            raise ValueError(msg)
        return value

    @field_validator("csrf_token")
    @classmethod
    def validate_csrf_token(cls, value: str) -> str:
        if not value:
            msg = "Missing CSRF token."
            raise ValueError(msg)
        return value
