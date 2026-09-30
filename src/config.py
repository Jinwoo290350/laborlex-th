from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = ""
    iapp_api_key: str = ""
    jev_api_key: str = ""
    database_url: str = "postgresql://laborlex:laborlex@127.0.0.1:5432/laborlex"
    decider: str = "openthai"
    app_password: str = ""


settings = Settings()
