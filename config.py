# Logic of AIDBOX operation has to be here.

from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
from urllib.parse import quote_plus
from pydantic import field_validator, ConfigDict

class Settings(BaseSettings):
    # API Settings
    API_VERSION: str = "1.0.0"
    API_TITLE: str = "FoodHak Health API"
    API_DESCRIPTION: str = "API for managing health device connections and data"
    
    # Database Settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 9988
    DB_NAME: str = "postgres"
    DB_USER: str = "admin"
    DB_PASSWORD: str = "admin123"
    DB_SCHEMA: str = "public"
    DATABASE_CHECK_ENABLED: bool = True

    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from individual components"""
        # URL encode the password to handle special characters
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"postgresql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Timestream Settings
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "eu-west-1"
    TIMESTREAM_DATABASE: str = "HealthDataDB"
    TIMESTREAM_TABLE: str = "healthMetrics"
    TIMESTREAM_CHECK_ENABLED: bool = True
    AWS_ACCOUNT_ID: str = "469379297648"
    ENVIRONMENT: str = "dev"

    # Health Check Settings
    HEALTH_CHECK_SERVICES_STR: str = "database,timestream"  # Store as string
    HEALTH_CHECK_TIMEOUT: int = 5  # seconds

    def get_health_check_services(self) -> List[str]:
        """Get list of health check services"""
        return [service.strip() for service in self.HEALTH_CHECK_SERVICES_STR.split(',') if service.strip()]

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow"  # Allow extra fields
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()