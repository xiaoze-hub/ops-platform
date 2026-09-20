from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "ops"
    db_password: str = "ops_dev_password"
    db_name: str = "ops_platform"
    secret_key: str = "dev-secret-change-me"
    admin_password: str = "admin123456"
    project_deploy_enabled: bool = False
    metrics_retention_days: int = 7
    logs_retention_days: int = 3
    online_threshold_seconds: int = 30
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    ws_log_interval_seconds: float = 2.0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
