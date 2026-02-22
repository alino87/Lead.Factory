from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    api_factory_key: str   # Pflichtfeld – Server startet nicht ohne diesen Key

    model_config = {"env_file": ".env"}


settings = Settings()
