from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CampusBite API"
    database_url: str = "postgresql+psycopg://campusbite:campusbite-local@localhost:5432/campusbite"
    jwt_secret_key: str = "development-only-change-before-use"
    jwt_access_token_expire_minutes: int = 60
    openai_api_key: str | None = None
    openai_model: str | None = None
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
