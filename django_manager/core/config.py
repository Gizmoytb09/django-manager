"""
Django Manager — Core constants, theme, and shared config.
"""

APP_VERSION = "0.1.0"
APP_NAME    = "Django Manager"

# ── Python versions offered in the wizard ──────────────────────────────────
PYTHON_VERSIONS = [
    {"label": "3.10", "badge": None},
    {"label": "3.11", "badge": None},
    {"label": "3.12", "badge": "LATEST"},
]

# ── Django versions with compatibility info ─────────────────────────────────
DJANGO_VERSIONS = [
    {"label": "4.2", "tag": "LTS",    "lts": True},
    {"label": "5.0", "tag": "LTS",    "lts": True},
    {"label": "5.1", "tag": "stable", "lts": False},
    {"label": "5.2", "tag": "latest", "lts": False},
]

# ── Starter packs ───────────────────────────────────────────────────────────
STARTER_PACKS = [
    {
        "id":       "htmx",
        "name":     "Django HTMX Stack",
        "icon":     "⚡",
        "desc":     "Build interactive Django apps without JavaScript. "
                    "HTMX handles dynamic updates directly from your templates.",
        "packages": ["django", "django-htmx"],
        "tags":     ["no JS required", "template-driven", "HTMX 1.19"],
        "available": True,
    },
    {
        "id":       "drf",
        "name":     "Django REST Stack",
        "icon":     "🔌",
        "desc":     "Django + DRF + SimpleJWT — full REST API setup.",
        "packages": ["django", "djangorestframework", "djangorestframework-simplejwt"],
        "tags":     ["REST API", "JWT auth"],
        "available": False,
    },
    {
        "id":       "auth",
        "name":     "Django Auth Stack",
        "icon":     "🔐",
        "desc":     "django-allauth with social login support.",
        "packages": ["django", "django-allauth"],
        "tags":     ["social login", "allauth"],
        "available": False,
    },
]

# ── CSS design tokens (used inline where Textual CSS can't reach) ───────────
THEME = {
    "bg":           "#0a0a0a",
    "bg2":          "#0f0f0f",
    "bg3":          "#111111",
    "green":        "#44B78B",
    "green_dim":    "#1e6e42",
    "green_dark":   "#092E20",
    "green_hi":     "#6ddba8",
    "muted":        "#2a2a2a",
    "text":         "#888888",
    "text_dim":     "#3a3a3a",
    "yellow":       "#e5c07b",
    "red":          "#e06c75",
    "blue":         "#61afef",
    "cyan":         "#56b6c2",
}

# ── Known django management commands (for smart prefix detection) ───────────
DJANGO_BUILTIN_COMMANDS = {
    "check", "compilemessages", "createcachetable", "dbshell",
    "diffsettings", "dumpdata", "flush", "inspectdb", "loaddata",
    "makemessages", "makemigrations", "migrate", "optimizemigration",
    "runserver", "sendtestemail", "shell", "showmigrations",
    "sqlflush", "sqlmigrate", "sqlsequencereset", "squashmigrations",
    "startapp", "startproject", "test", "testserver", "collectstatic",
}

# ── Manager's own commands ──────────────────────────────────────────────────
MANAGER_COMMANDS = {
    "create", "open", "docs", "settings", "add",
    "update", "lock", "tui", "env",
}
