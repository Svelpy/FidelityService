from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development","staging","production","test"]

class Settings(BaseSettings):
    """Configuración de la aplicación usando variables de entorno"""
    
    # =================================
    # Application
    # =================================
    APP_NAME: str = "Proyect_Service_API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = """Lorep Ipsum"""
    ENVIRONMENT: Environment = "development"    
    # =================================
    # PostgreSQL
    # =================================
    DATABASE_URL: str | None = None
    TEST_DATABASE_URL: str | None = None
    # =================================
    # JWT
    # =================================
    SECRET_KEY: str
    CSRF_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    # =================================
    # Cloudinary
    # =================================
    CLOUDINARY_CLOUD_NAME: str = None
    CLOUDINARY_API_KEY: str = None
    CLOUDINARY_API_SECRET: str = None
    CLOUDINARY_FOLDER_NAME: str = None
    # =================================
    # CORS
    # =================================
    DEV_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    PROD_ORIGINS: str = None
    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:


        if self.ENVIRONMENT in {"development", "test"}:
            origins = self.DEV_ORIGINS
        else:
            origins = self.PROD_ORIGINS
        if not origins:
            raise ValueError("Debe configurarse PROD_ORIGINS en producción")
        return [origin.strip() for origin in origins.split(",") if origin.strip()]

    ACCESS_TOKEN_EXPIRE_MINUTES_DEVELOPMENT: int = 60
    ACCESS_TOKEN_EXPIRE_MINUTES_STAGING: int = 15
    ACCESS_TOKEN_EXPIRE_MINUTES_PRODUCTION: int = 15
    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        durations = {
            "development": self.ACCESS_TOKEN_EXPIRE_MINUTES_DEVELOPMENT,
            "staging": self.ACCESS_TOKEN_EXPIRE_MINUTES_STAGING,
            "production": self.ACCESS_TOKEN_EXPIRE_MINUTES_PRODUCTION,
            "test": self.ACCESS_TOKEN_EXPIRE_MINUTES_DEVELOPMENT,
        }
        return durations[self.ENVIRONMENT]

    REFRESH_TOKEN_EXPIRE_DAYS_DEVELOPMENT: int = 7
    REFRESH_TOKEN_EXPIRE_DAYS_STAGING: int = 7
    REFRESH_TOKEN_EXPIRE_DAYS_PRODUCTION: int = 7
    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        durations = {
            "development": self.REFRESH_TOKEN_EXPIRE_DAYS_DEVELOPMENT,
            "staging": self.REFRESH_TOKEN_EXPIRE_DAYS_STAGING,
            "production": self.REFRESH_TOKEN_EXPIRE_DAYS_PRODUCTION,
            "test": self.REFRESH_TOKEN_EXPIRE_DAYS_DEVELOPMENT,
        }
        return durations[self.ENVIRONMENT]

    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    @property
    def REFRESH_TOKEN_COOKIE_SECURE(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}
    
    @property
    def DEBUG(self) -> bool:
        return self.ENVIRONMENT == "development"


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
@lru_cache
def get_settings() -> Settings:
    return Settings()

