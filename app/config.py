"""
Configuration centrale de l'application.
Lit les variables depuis le fichier .env de manière sécurisée.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres de l'application, chargés depuis .env."""

    # Base de données
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str

    # Sécurité
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Environnement
    ENVIRONMENT: str = "development"

    @property
    def database_url(self) -> str:
        """Construit l'URL de connexion PostgreSQL."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Instance unique réutilisée dans toute l'application
settings = Settings()
