from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Base de données
    DB_USER: str = "fintech_user"
    DB_PASSWORD: str = "changez_ce_mot_de_passe"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "fintech_gabon"

    # JWT
    SECRET_KEY: str = "CHANGEZ_EN_PROD"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # OTP
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_RESEND: int = 3          # anti-abus : max renvois par fenêtre
    OTP_RESEND_WINDOW_MINUTES: int = 60

    # Sécurité login
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Environnement
    ENVIRONMENT: str = "development"
    APP_NAME: str = "FinTech Gabon"
    VERSION: str = "0.1.0"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"


settings = Settings()
