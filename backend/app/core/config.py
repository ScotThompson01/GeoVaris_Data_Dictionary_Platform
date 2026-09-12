from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_env:str="development"
    app_name:str="GeoVaris Data Dictionary Platform"
    database_url:str
    frontend_origin:str="http://localhost:3000"
    model_config=SettingsConfigDict(env_file=".env",extra="ignore",case_sensitive=False)
settings=Settings()
