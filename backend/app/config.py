"""Environment-driven configuration. All values have safe local defaults so the
stack boots on a fresh clone with no manual .env setup."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_dsn: str = "postgresql+psycopg2://ev:ev@postgres:5432/ev_orchestrator"
    redis_url: str = "redis://redis:6379/0"
    mqtt_host: str = "mosquitto"
    mqtt_port: int = 1883
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    twin_engine_http_url: str = "http://twin-engine:8100"
    twin_engine_ws_url: str = "ws://twin-engine:8100/ws"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Seeded once at startup if no admin exists yet - see app/seed.py. Change
    # these via .env before first boot; printed to the backend log once so
    # you're not locked out.
    admin_seed_email: str = "admin@meridiangrid.local"
    admin_seed_password: str = "change-me-admin-2026"
    admin_seed_name: str = "MeridianGrid Admin"

    # Google Sign-In: real OAuth, verified server-side against Google's
    # public keys. Leave unset to keep the button visibly "not configured"
    # rather than silently failing. Get a free Client ID from
    # https://console.cloud.google.com/apis/credentials (OAuth 2.0 Client ID,
    # type "Web application").
    google_oauth_client_id: str | None = None


settings = Settings()
