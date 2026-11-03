from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_env:str="development"
    app_name:str="GeoVaris Data Dictionary Platform"
    database_url:str
    frontend_origin:str="http://localhost:3000"

    # Phase 5E execution admission remains disabled until persistent
    # ownership, capacity reservations, and recovery are implemented.
    dq_execution_admission_enabled: bool = False

    # Zero deliberately fails the execution capacity policy.
    # A positive installation ceiling must be explicitly configured.
    dq_execution_max_concurrent: int = 0

    # PostgreSQL verification is disabled until explicitly configured.
    postgresql_verification_enabled: bool = False

    # Comma-separated approved host:port destinations.
    postgresql_verification_allowed_destinations: str = ""

    # Client-managed trusted CA certificate path.
    postgresql_verification_ssl_root_cert: str = ""

    # Comma-separated client-approved IPv4/IPv6 CIDR networks.
    # Empty means no network destinations are authorized.
    postgresql_verification_allowed_ip_networks: str = ""

    model_config=SettingsConfigDict(env_file=".env",extra="ignore",case_sensitive=False)
settings=Settings()
