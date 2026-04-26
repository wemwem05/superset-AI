"""
Apache Superset configuration file.
All settings can be overridden via environment variables.
See https://superset.apache.org/docs/configuration/configuring-superset
"""

import os
from datetime import timedelta

import redis

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
# IMPORTANT: Generate once with `openssl rand -base64 42` and store in .env
# Never rotate after first deployment — it encrypts saved database credentials.
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://"
    f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['DATABASE_HOST']}:{os.environ['DATABASE_PORT']}"
    f"/{os.environ['POSTGRES_DB']}"
)

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "ALERT_REPORTS": True,
    "ESCAPE_MARKDOWN_HTML": False,
}

# Allow style/SVG tags in Handlebars charts (needed for custom gauge)
HTML_SANITIZATION_SCHEMA_EXTENSIONS = {
    "attributes": {
        "*": ["style", "className"],
        "svg": ["xmlns", "height", "viewBox", "width", "fill"],
        "circle": [
            "cx", "cy", "r", "stroke", "stroke-width", "fill",
            "stroke-dasharray", "stroke-dashoffset", "stroke-linecap",
            "transform",
        ],
        "text": [
            "x", "y", "text-anchor", "dominant-baseline",
            "font-size", "font-weight", "fill", "font-family",
        ],
        "path": ["d", "fill", "stroke", "stroke-width"],
        "line": ["x1", "y1", "x2", "y2", "stroke", "stroke-width"],
        "linearGradient": ["id", "x1", "y1", "x2", "y2"],
        "stop": ["offset", "stop-color", "stop-opacity"],
        "defs": [],
    },
    "tagNames": ["style", "svg", "circle", "text", "path", "g", "defs", "linearGradient", "stop", "line"],
}

# ---------------------------------------------------------------------------
# Cache (Redis)
# ---------------------------------------------------------------------------
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"

# General Superset cache (metadata, UI state): 5 min — low-cost to recompute
CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,       # 5 min
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_URL": f"{REDIS_URL}/0",
}

# Query result cache: 30 min — PostgreSQL source data refreshes at most hourly
DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 1800,      # 30 min (increased from 5 min)
    "CACHE_KEY_PREFIX": "superset_data_",
    "CACHE_REDIS_URL": f"{REDIS_URL}/1",
}

# Filter state: 10 min — session-like user interaction state
FILTER_STATE_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 600,       # 10 min
    "CACHE_KEY_PREFIX": "superset_filter_",
    "CACHE_REDIS_URL": f"{REDIS_URL}/2",
}

# Explore form data: 10 min — temporary visualization builder state
EXPLORE_FORM_DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 600,       # 10 min
    "CACHE_KEY_PREFIX": "superset_explore_",
    "CACHE_REDIS_URL": f"{REDIS_URL}/3",
}

# ---------------------------------------------------------------------------
# Celery (async queries, alerts & reports)
# ---------------------------------------------------------------------------
class CeleryConfig:
    broker_url = f"{REDIS_URL}/4"
    result_backend = f"{REDIS_URL}/5"
    imports = ("superset.sql_lab", "superset.tasks.scheduler")
    task_annotations = {
        "sql_lab.get_sql_results": {"rate_limit": "100/s"},
    }
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": timedelta(minutes=1),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": timedelta(days=1),
        },
    }


CELERY_CONFIG = CeleryConfig

# ---------------------------------------------------------------------------
# Server-side sessions (Redis) — prevents random logouts
# ---------------------------------------------------------------------------
SESSION_TYPE = "redis"
SESSION_REDIS = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=6)
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

# ---------------------------------------------------------------------------
# Security & Production Hardening
# ---------------------------------------------------------------------------
WTF_CSRF_ENABLED = True
SESSION_COOKIE_NAME = "superset_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Enable these when behind HTTPS reverse proxy (Nginx, ALB, or Caddy):
# SESSION_COOKIE_SECURE = True
# SESSION_COOKIE_SAMESITE = "Strict"
TALISMAN_ENABLED = False  # enable when behind HTTPS reverse proxy
# TALISMAN_CONFIG = {
#     "force_https": True,
#     "session_cookie_secure": True,
#     "content_security_policy": {
#         "default-src": ["'self'"],
#         "img-src": ["'self'", "data:", "blob:"],
#         "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
#         "style-src": ["'self'", "'unsafe-inline'"],
#         "worker-src": ["'self'", "blob:"],
#         "connect-src": ["'self'"],
#         "object-src": ["'none'"],
#         "base-uri": ["'self'"],
#     },
# }

# Increase row limit for production use
ROW_LIMIT = 50000
SQL_MAX_ROW = 100000

# Prevent browser from caching sensitive responses
SEND_FILE_MAX_AGE_DEFAULT = 0

# ---------------------------------------------------------------------------
# Currency formats (adds to the UI dropdown in chart formatting options)
# ---------------------------------------------------------------------------
CURRENCIES = ["USD", "EUR", "GBP", "KZT", "UZS", "RUB"]

# Mapbox (optional)
MAPBOX_API_KEY = os.environ.get("MAPBOX_API_KEY", "")
