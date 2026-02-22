from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://malin:malin_dev@localhost:5432/malin"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "malin-documents"
    s3_use_ssl: bool = False
    master_tenant_key: str = "dev-tenant-key-change-me"

    # Alembic uses sync driver
    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2").replace(
            "postgresql://", "postgresql+psycopg2://"
        )

    model_config = {"env_file": ".env"}


settings = Settings()
