from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # role app (nunca postgres/root)
    database_url: str
    mongo_url: str
    mongo_db: str = "music"
    redis_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_url(self) -> str:
        # o driver instalado é o psycopg v3
        return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)


settings = Settings()