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
    # Starlette's CORSMiddleware hard-400s the preflight itself for any
    # origin not in an explicit list - a custom FRONTEND_PORT, a network-IP
    # origin, or any other reasonable variant of "wherever the frontend
    # happens to be served from" would otherwise break every API call
    # before it even reaches a route handler, surfacing only as a generic
    # frontend error with nothing in the backend logs to explain it (that's
    # exactly what happened here). Wildcarding the origin is safe only
    # because this app carries no CORS "credentials" (browser-managed
    # cookies) to leak - auth is a Bearer token in a normal header, sent
    # with fetch()'s default credentials mode, which CORS doesn't treat as
    # credentialed - so allow_origins=["*"] + allow_credentials=False (the
    # only combination the CORS spec permits for a wildcard origin) can't
    # expose anything a same-origin request couldn't already reach.
    cors_origins: list[str] = ["*"]

    # Seeded once at startup if no admin exists yet - see app/seed.py. Change
    # these via .env before first boot; printed to the backend log once so
    # you're not locked out.
    admin_seed_email: str = "admin@meridiangrid.local"
    admin_seed_password: str = "change-me-admin-2026"
    admin_seed_name: str = "MeridianGrid Admin"

    # Google Sign-In via Firebase Authentication: the frontend runs Firebase's
    # Google sign-in popup and hands us the resulting Firebase ID token,
    # verified server-side with `google.oauth2.id_token.verify_firebase_token`
    # against the project ID below - no Firebase Admin SDK or service-account
    # key needed, matching this project's zero-cost/no-extra-secrets stance.
    # Leave unset to keep the button visibly "not configured" rather than
    # silently failing. Get the project ID from your Firebase project
    # settings (also the `projectId` field of the same web app config the
    # frontend needs - see .env.example's VITE_FIREBASE_* variables).
    firebase_project_id: str | None = None

    # Resend (https://resend.com) for the OTP account-confirmation email
    # sent on password registration. Leave unset to keep working in dev: the
    # OTP is still generated and required, just logged server-side instead
    # of emailed - see app/email_service.py. onboarding@resend.dev is
    # Resend's own sandbox sender, usable with no domain verification but
    # restricted by Resend to only deliver to the address that owns the API
    # key - point RESEND_FROM_EMAIL at a verified domain of your own once
    # you have one, to email real users.
    resend_api_key: str | None = None
    resend_from_email: str = "onboarding@resend.dev"
    otp_expire_minutes: int = 10


settings = Settings()
