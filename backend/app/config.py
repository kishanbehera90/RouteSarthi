"""App configuration, loaded from backend/.env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    redis_url: str = ""
    # Real road-routing for first/last-mile legs (app/roads.py), tried as a
    # chain, each step used only if the previous is absent or its circuit
    # breaker is open (e.g. a rate-limited backend fails over to the next):
    #   osrm_url        self-hosted OSRM — fastest, no rate limit (primary if set)
    #   ors_api_key     OpenRouteService hosted free tier (~2000/day, 40/min)
    #   geoapify_api_key Geoapify hosted free tier (~3000/day) — second free
    #                   quota so hitting one provider's limit fails over to the
    #                   other instead of dropping to haversine
    #   -> haversine estimate when none answer.
    # All optional; road legs still work (haversine) with none configured.
    ors_api_key: str = ""
    osrm_url: str = ""
    geoapify_api_key: str = ""
    # RapidAPI (IRCTC1) — free tier is ~10 calls/month, so every use must be
    # budget-guarded. Used for train-validity spot checks / lazy refresh.
    rapidapi_key: str = ""

    # --- Auth ---
    # Must be byte-identical across every process (unlike DB/graph, which
    # degrade gracefully without config) — an auto-generated per-process
    # secret would cause intermittent 401s under multiple workers. auth.py
    # raises a clear error lazily if this is unset; nothing else depends on it.
    secret_key: str = ""
    # Password-reset email via Brevo's HTTPS API (v3/smtp/email), NOT raw SMTP.
    # Render's free tier blocks outbound traffic to SMTP ports 25/465/587
    # entirely (as of Sep 2025) — a correctly-configured SMTP login still hangs
    # until timeout there. The API travels over normal HTTPS (443), which is
    # never blocked, so this is the fix, not a workaround. Brevo free tier:
    # 300/day. Get the key at app.brevo.com -> SMTP & API -> API Keys (this is
    # a DIFFERENT key from the SMTP login/password pair). Empty brevo_api_key
    # or brevo_from_email = forgot-password silently no-ops (logs the reset
    # link instead of emailing it) rather than failing the request.
    brevo_api_key: str = ""
    smtp_from_email: str = ""  # the sender address you verified in Brevo
    # Used to build the reset-password link emailed to the user.
    frontend_url: str = "http://localhost:5173"
    # Extra CORS origins for prod (comma-separated), added to the dev-origin
    # defaults in main.py — e.g. the deployed Vercel URL.
    cors_origins: str = ""


settings = Settings()
