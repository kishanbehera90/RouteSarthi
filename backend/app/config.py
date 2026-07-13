"""App configuration, loaded from backend/.env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    redis_url: str = ""
    # Real road-routing for first/last-mile legs (app/roads.py). ors_api_key
    # (OpenRouteService, free tier, simple signup) is the default path — set
    # osrm_url instead to switch to a self-hosted OSRM instance at any time,
    # no code changes needed; osrm_url takes priority when both are set. Both
    # optional — with neither set, road legs fall back to the haversine
    # estimate that existed before real road-routing.
    ors_api_key: str = ""
    osrm_url: str = ""
    # RapidAPI (IRCTC1) — free tier is ~10 calls/month, so every use must be
    # budget-guarded. Used for train-validity spot checks / lazy refresh.
    rapidapi_key: str = ""

    # --- Auth ---
    # Must be byte-identical across every process (unlike DB/graph, which
    # degrade gracefully without config) — an auto-generated per-process
    # secret would cause intermittent 401s under multiple workers. auth.py
    # raises a clear error lazily if this is unset; nothing else depends on it.
    secret_key: str = ""
    # SMTP (password-reset emails) — Brevo's free tier (300/day). Chosen over
    # Resend's sandbox sender because Brevo only requires verifying a single
    # SENDER EMAIL (a confirmation-link click, no DNS/domain needed) to send
    # to any recipient; Resend's unverified-domain sandbox can only send to
    # the account owner's own email. Empty smtp_user = forgot-password
    # silently no-ops (logs the reset link instead of emailing it).
    smtp_host: str = "smtp-relay.brevo.com"
    smtp_port: int = 587
    smtp_user: str = ""       # Brevo account login email
    smtp_password: str = ""  # Brevo SMTP key (NOT your account password)
    smtp_from_email: str = ""  # the sender address you verified in Brevo
    # Used to build the reset-password link emailed to the user.
    frontend_url: str = "http://localhost:5173"
    # Extra CORS origins for prod (comma-separated), added to the dev-origin
    # defaults in main.py — e.g. the deployed Vercel URL.
    cors_origins: str = ""


settings = Settings()
