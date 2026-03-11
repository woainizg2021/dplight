from typing import List, Optional, Dict
from pydantic import AnyHttpUrl, EmailStr, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Dplight ERP"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    MSSQL_SERVER: str = "43.156.110.64"
    MSSQL_USER: str = "sa"
    MSSQL_PASSWORD: str = "yangjgsj123,."
    MSSQL_DB_GROUP1: str = "T100_S1"
    MSSQL_DB_GROUP2: str = "T100_S2"
    
    MYSQL_SERVER: str = "43.156.110.64"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "yangjgsj123,."
    MYSQL_DB: str = "dplight_erp"

    # Security
    SECRET_KEY: str = "your-secret-key-please-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # AI
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str

    # WeCom Webhooks
    WX_WEBHOOK_UGANDA: str
    WX_WEBHOOK_KENYA: str

    # Sensitive Passwords
    DEFAULT_PASSWORD: str
    PROFIT_SECRET_KEY: str

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
