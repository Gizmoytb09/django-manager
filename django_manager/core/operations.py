"""
Django Manager — Core operations.
All uv and Django subprocess calls are here. Screens call these functions
and receive results through Textual workers / async generators.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Optional

import importlib.util

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore


# ── Result types ────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    ok:      bool
    message: str
    detail:  str = ""


@dataclass
class ProjectConfig:
    name:         str
    location:     Path
    python_ver:   str
    django_ver:   str
    starter_pack: str
    packages:     list[str] = field(default_factory=list)
    venv_dir:     Optional[Path] = None
    interactive:  str = "htmx"
    css_framework: str = "bootstrap"
    auth_framework: str = "django"
    add_pytest:   bool = False
    skip_auth_app: bool = False
    custom_user:  bool = False
    run_migrations: bool = True

    @property
    def path(self) -> Path:
        return self.location / self.name

    @property
    def venv_path(self) -> Path:
        return self.venv_dir if self.venv_dir else (self.path / ".venv")

    @property
    def activate_script(self) -> Path:
        if os.name == "nt":
            return self.venv_path / "Scripts" / "activate.bat"
        return self.venv_path / "bin" / "activate"


# ── uv detection ────────────────────────────────────────────────────────────

def uv_available() -> bool:
    return shutil.which("uv") is not None or importlib.util.find_spec("uv") is not None


def uv_cmd(venv_path: Optional[Path] = None, ensure: bool = False) -> list[str]:
    if venv_path:
        venv_uv = _venv_bin(venv_path, "uv")
        if venv_uv and venv_uv.exists():
            return [str(venv_uv)]
        if _venv_has_module(venv_path, "uv"):
            return [str(venv_python(venv_path)), "-m", "uv"]

    path = shutil.which("uv")
    if path:
        return [path]

    compiled = getattr(sys, "frozen", False) or bool(globals().get("__compiled__", False))
    if not compiled:
        if importlib.util.find_spec("uv") is not None:
            return [sys.executable, "-m", "uv"]

    if ensure:
        # Try installing uv into the project venv first, otherwise current env.
        if venv_path and venv_python(venv_path).exists():
            result = _pip_install_uv(venv_python(venv_path))
            if result.returncode == 0:
                return uv_cmd(venv_path=venv_path, ensure=False)
        if not compiled:
            result = _pip_install_uv(Path(sys.executable))
            if result.returncode == 0:
                return uv_cmd(venv_path=None, ensure=False)
        raise FileNotFoundError(
            "uv not found and auto-install failed. Install with: pip install uv "
            "(or winget install --id=astral-sh.uv -e)"
        )

    raise FileNotFoundError(
        "uv not found. Install with: pip install uv (or winget install --id=astral-sh.uv -e)"
    )


# ── Project creation — async step generator ─────────────────────────────────

async def create_project(
    cfg: ProjectConfig,
) -> AsyncGenerator[tuple[str, StepResult], None]:
    """
    Yields (step_id, StepResult) tuples as each step completes.
    Steps: mkdir, venv, activate, install, startproject, lockfile, auth, migrate
    """
    uv = uv_cmd(ensure=True)

    # 1. Create directory
    try:
        cfg.path.mkdir(parents=True, exist_ok=False)
        yield "mkdir", StepResult(ok=True, message="Project directory created",
                                  detail=str(cfg.path))
    except FileExistsError:
        yield "mkdir", StepResult(ok=False, message="Directory already exists",
                                  detail=str(cfg.path))
        return
    except Exception as e:
        yield "mkdir", StepResult(ok=False, message="Failed to create directory", detail=str(e))
        return

    await asyncio.sleep(0.3)

    # 2. Create venv
    result = await _run(
        [*uv, "venv", "--python", cfg.python_ver, str(cfg.venv_path)],
        cwd=cfg.path,
    )
    yield "venv", StepResult(
        ok=result.returncode == 0,
        message="Virtual environment created" if result.returncode == 0 else "venv creation failed",
        detail=_combined_output(result),
    )
    if result.returncode != 0:
        return

    await asyncio.sleep(0.2)

    # 3. "Activate" — in subprocess context we set env vars
    yield "activate", StepResult(ok=True, message="Virtual environment activated",
                                 detail=str(cfg.venv_path))

    await asyncio.sleep(0.3)

    # 4. Install Django (needed for startproject)
    try:
        ensure_pyproject(cfg)
    except Exception as e:
        yield "install", StepResult(ok=False, message="Package install failed", detail=str(e))
        return

    result = await _run(
        [*uv, "pip", "install", f"django=={cfg.django_ver}"],
        cwd=cfg.path,
        env=_venv_env(cfg),
    )
    yield "install", StepResult(
        ok=result.returncode == 0,
        message=f"Installed: django=={cfg.django_ver}" if result.returncode == 0 else "Package install failed",
        detail=_combined_output(result),
    )
    if result.returncode != 0:
        return

    await asyncio.sleep(0.2)

    # 5. django-admin startproject
    django_admin = cfg.venv_path / ("Scripts/django-admin" if os.name == "nt" else "bin/django-admin")
    result = await _run(
        [str(django_admin), "startproject", cfg.name, "."],
        cwd=cfg.path,
        env=_venv_env(cfg),
    )
    yield "startproject", StepResult(
        ok=result.returncode == 0,
        message="Django project structure created" if result.returncode == 0 else "startproject failed",
        detail=_combined_output(result),
    )
    if result.returncode != 0:
        return

    await asyncio.sleep(0.2)

    # 6. Add dependencies + lock
    packages = [f"django=={cfg.django_ver}"] + [
        p for p in cfg.packages if p != "django"
    ]
    result = await _run(
        [*uv, "add", *packages],
        cwd=cfg.path,
        env=_venv_env(cfg),
    )
    if result.returncode != 0:
        yield "lockfile", StepResult(
            ok=False,
            message="Lock generation failed",
            detail=_combined_output(result),
        )
        return

    result = await _run([*uv, "lock"], cwd=cfg.path, env=_venv_env(cfg))
    yield "lockfile", StepResult(
        ok=result.returncode == 0,
        message="pyproject.toml + uv.lock generated" if result.returncode == 0 else "Lock generation failed",
        detail=_combined_output(result),
    )
    if result.returncode != 0:
        return

    await asyncio.sleep(0.2)

    # 6b. Static/media + base template + helper JS
    ok, detail = await _setup_project_assets(cfg)
    yield "assets", StepResult(
        ok=ok,
        message="Static/media + base template created" if ok else "Static/media setup failed",
        detail=detail,
    )
    if not ok:
        return

    await asyncio.sleep(0.2)

    # 7. Auth app + scaffolding (optional)
    if cfg.skip_auth_app:
        yield "auth", StepResult(ok=True, message="Auth scaffold skipped")
    else:
        ok, detail = await _setup_auth_scaffold(cfg)
        yield "auth", StepResult(
            ok=ok,
            message="Authentication scaffold created" if ok else "Auth scaffold failed",
            detail=detail,
        )
        if not ok:
            return

    await asyncio.sleep(0.2)

    # 8. Migrations (optional)
    if cfg.run_migrations and not cfg.skip_auth_app:
        ok, detail = await _run_migrations(cfg)
        yield "migrate", StepResult(
            ok=ok,
            message="Database migrations applied" if ok else "Migrations failed",
            detail=detail,
        )
        if not ok:
            return
    else:
        yield "migrate", StepResult(ok=True, message="Migrations skipped")


# ── Django command runner ────────────────────────────────────────────────────

async def run_django_command(
    project_path: Path,
    command: str,
    args: list[str],
    python_ver: str,
    venv_path: Optional[Path] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream output lines from: python manage.py <command> [args]
    """
    venv_python = _python_bin(project_path, venv_path)
    manage_py   = project_path / "manage.py"
    if not manage_py.exists():
        raise FileNotFoundError(f"manage.py not found at {manage_py}")

    env = venv_env_from_path(venv_path) if venv_path else None
    proc = await asyncio.create_subprocess_exec(
        str(venv_python), str(manage_py), command, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=project_path,
        env=env,
    )

    async for line in proc.stdout:
        yield line.decode("utf-8", errors="replace").rstrip("\n")

    await proc.wait()


async def start_runserver(
    project_path: Path,
    port: int = 8000,
    venv_path: Optional[Path] = None,
) -> asyncio.subprocess.Process:
    """
    Start `python manage.py runserver` as a long-running process.
    Caller is responsible for streaming proc.stdout and calling proc.terminate().
    """
    venv_python = _python_bin(project_path, venv_path)
    manage_py   = project_path / "manage.py"
    if not manage_py.exists():
        raise FileNotFoundError(f"manage.py not found at {manage_py}")

    env = venv_env_from_path(venv_path) if venv_path else None
    proc = await asyncio.create_subprocess_exec(
        str(venv_python), str(manage_py), "runserver", f"0.0.0.0:{port}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=project_path,
        env=env,
    )
    return proc


# ── Package helpers (uv) ─────────────────────────────────────────────────────

async def uv_add_packages(
    project_path: Path,
    packages: list[str],
    venv_path: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    uv = uv_cmd(venv_path=venv_path, ensure=True)
    env = venv_env_from_path(venv_path) if venv_path else None
    return await _run([*uv, "add", *packages], cwd=project_path, env=env)


async def uv_remove_packages(
    project_path: Path,
    packages: list[str],
    venv_path: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    uv = uv_cmd(venv_path=venv_path, ensure=True)
    env = venv_env_from_path(venv_path) if venv_path else None
    return await _run([*uv, "remove", *packages], cwd=project_path, env=env)


async def uv_list_packages(
    project_path: Path,
    venv_path: Optional[Path] = None,
) -> list[str]:
    uv = uv_cmd(venv_path=venv_path, ensure=True)
    env = venv_env_from_path(venv_path) if venv_path else None
    result = await _run([*uv, "pip", "list", "--format=freeze"], cwd=project_path, env=env)
    if result.returncode == 0 and result.stdout.strip():
        pkgs: list[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            name = line.split("==", 1)[0]
            pkgs.append(name)
        return pkgs
    return read_project_dependencies(project_path)


def read_project_dependencies(project_path: Path) -> list[str]:
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists() and tomllib is not None:
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project = data.get("project", {})
            deps = list(project.get("dependencies") or [])
            return deps
        except Exception:
            pass
    req = project_path / "requirements.txt"
    if req.exists():
        deps: list[str] = []
        for line in req.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            deps.append(line)
        return deps
    return []

# ── Helpers ──────────────────────────────────────────────────────────────────

async def _run(
    cmd: list[str],
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


def _combined_output(result: subprocess.CompletedProcess) -> str:
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if out and err:
        return out + "\n" + err
    return out or err


async def _run_manage(cfg: ProjectConfig, args: list[str]) -> subprocess.CompletedProcess:
    manage_py = cfg.path / "manage.py"
    return await _run(
        [str(_python_bin(cfg.path, cfg.venv_path)), str(manage_py), *args],
        cwd=cfg.path,
        env=_venv_env(cfg),
    )


async def _setup_auth_scaffold(cfg: ProjectConfig) -> tuple[bool, str]:
    """Create authentication app, templates, and settings/urls wiring."""
    # 1) startapp authentication
    result = await _run_manage(cfg, ["startapp", "authentication"])
    if result.returncode != 0:
        return False, _combined_output(result)

    # 2) write app files
    auth_dir = cfg.path / "authentication"
    templates_dir = auth_dir / "templates"
    _write_file(auth_dir / "urls.py", _auth_urls(cfg.auth_framework))
    _write_file(auth_dir / "views.py", _auth_views(cfg.auth_framework))
    _write_file(auth_dir / "forms.py", _auth_forms())

    _write_file(templates_dir / "authentication" / "base.html", _auth_base_template(cfg.css_framework))
    if cfg.auth_framework == "allauth":
        _write_file(templates_dir / "account" / "login.html", _allauth_login_template(cfg.css_framework))
        _write_file(templates_dir / "account" / "signup.html", _allauth_signup_template(cfg.css_framework))
        _write_file(templates_dir / "account" / "logout.html", _allauth_logout_template(cfg.css_framework))
    else:
        _write_file(templates_dir / "authentication" / "login.html", _auth_login_template(cfg.css_framework))
        _write_file(templates_dir / "authentication" / "signup.html", _auth_signup_template(cfg.css_framework))

    # 3) update project settings + urls
    settings_path = cfg.path / cfg.name / "settings.py"
    urls_path = cfg.path / cfg.name / "urls.py"
    if settings_path.exists():
        settings_text = settings_path.read_text(encoding="utf-8")
        settings_text = _insert_list_entries(
            settings_text,
            "INSTALLED_APPS",
            ["authentication"] + _auth_installed_apps(cfg.auth_framework),
        )
    if cfg.auth_framework == "allauth":
        settings_text = _append_if_missing(
            settings_text,
            "\nSITE_ID = 1\n",
        )
        settings_text = _append_if_missing(
                settings_text,
                "\nAUTHENTICATION_BACKENDS = [\n"
                "    \"django.contrib.auth.backends.ModelBackend\",\n"
                "    \"allauth.account.auth_backends.AuthenticationBackend\",\n"
                "]\n",
            )
    if cfg.custom_user:
        settings_text = _append_if_missing(
            settings_text,
            "\nAUTH_USER_MODEL = \"authentication.CustomUser\"\n",
        )
        if cfg.interactive == "htmx":
            settings_text = _insert_list_entries(
                settings_text,
                "MIDDLEWARE",
                ["django_htmx.middleware.HtmxMiddleware"],
            )
        settings_path.write_text(settings_text, encoding="utf-8")

    if urls_path.exists():
        urls_text = urls_path.read_text(encoding="utf-8")
        urls_text = _ensure_include_import(urls_text)
        urls_text = _insert_list_entries(
            urls_text,
            "urlpatterns",
            ["path(\"auth/\", include(\"authentication.urls\"))"]
            + (["path(\"accounts/\", include(\"allauth.urls\"))"] if cfg.auth_framework == "allauth" else []),
        )
        urls_path.write_text(urls_text, encoding="utf-8")

    # 4) custom user model
    if cfg.custom_user:
        _write_file(auth_dir / "models.py", _auth_models_custom_user())

    return True, "authentication app + templates generated"


async def _setup_project_assets(cfg: ProjectConfig) -> tuple[bool, str]:
    """Create static/media dirs and base templates per CSS/JS choices."""
    settings_path = cfg.path / cfg.name / "settings.py"
    if not settings_path.exists():
        return False, "settings.py not found"

    static_dir = cfg.path / "static"
    media_dir = cfg.path / "media"
    static_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    js_dir = static_dir / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    _write_file(js_dir / "ajax.js", _ajax_helper_js())
    _write_file(js_dir / "jquery.js", _jquery_helper_js())

    templates_dir = cfg.path / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    _write_file(templates_dir / "base.html", _base_template(cfg.css_framework, cfg.interactive))

    settings_text = settings_path.read_text(encoding="utf-8")
    settings_text = _append_if_missing(
        settings_text,
        "\n# Static & media\n"
        "STATIC_URL = \"static/\"\n"
        "STATICFILES_DIRS = [BASE_DIR / \"static\"]\n"
        "MEDIA_URL = \"media/\"\n"
        "MEDIA_ROOT = BASE_DIR / \"media\"\n",
    )
    settings_path.write_text(settings_text, encoding="utf-8")

    # Create a modern homepage + skeleton app when a CSS framework is chosen
    if cfg.css_framework != "none":
        ok, detail = await _setup_skeleton_app(cfg)
        if not ok:
            return False, detail
    return True, "static/media + base template created"


async def _setup_skeleton_app(cfg: ProjectConfig) -> tuple[bool, str]:
    """Create a minimal skeleton app with a modern homepage."""
    result = await _run_manage(cfg, ["startapp", "skeleton"])
    if result.returncode != 0:
        return False, _combined_output(result)

    skel_dir = cfg.path / "skeleton"
    _write_file(skel_dir / "urls.py", _skeleton_urls())
    _write_file(skel_dir / "views.py", _skeleton_views())
    _write_file(
        skel_dir / "templates" / "skeleton" / "home.html",
        _skeleton_home_template(cfg.css_framework),
    )

    settings_path = cfg.path / cfg.name / "settings.py"
    if settings_path.exists():
        settings_text = settings_path.read_text(encoding="utf-8")
        settings_text = _insert_list_entries(
            settings_text,
            "INSTALLED_APPS",
            ["skeleton"],
        )
        settings_path.write_text(settings_text, encoding="utf-8")

    urls_path = cfg.path / cfg.name / "urls.py"
    if urls_path.exists():
        urls_text = urls_path.read_text(encoding="utf-8")
        urls_text = _ensure_include_import(urls_text)
        urls_text = _insert_list_entries(
            urls_text,
            "urlpatterns",
            ["path(\"\", include(\"skeleton.urls\"))"],
        )
        urls_path.write_text(urls_text, encoding="utf-8")

    return True, "skeleton app + homepage created"


async def _run_migrations(cfg: ProjectConfig) -> tuple[bool, str]:
    result = await _run_manage(cfg, ["makemigrations", "authentication"])
    if result.returncode != 0:
        return False, _combined_output(result)
    result = await _run_manage(cfg, ["migrate"])
    if result.returncode != 0:
        return False, _combined_output(result)
    return True, _combined_output(result)


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _auth_installed_apps(auth_framework: str) -> list[str]:
    if auth_framework != "allauth":
        return []
    return [
        "django.contrib.sites",
        "allauth",
        "allauth.account",
        "allauth.socialaccount",
    ]


def _auth_urls(auth_framework: str) -> str:
    if auth_framework == "allauth":
        return (
            "from django.urls import path\n"
            "from django.views.generic import RedirectView\n\n"
            "app_name = \"auth\"\n\n"
            "urlpatterns = [\n"
            "    path(\"login/\", RedirectView.as_view(url=\"/accounts/login/\"), name=\"login\"),\n"
            "    path(\"logout/\", RedirectView.as_view(url=\"/accounts/logout/\"), name=\"logout\"),\n"
            "    path(\"signup/\", RedirectView.as_view(url=\"/accounts/signup/\"), name=\"signup\"),\n"
            "]\n"
        )
    return (
        "from django.urls import path\n"
        "from . import views\n\n"
        "app_name = \"auth\"\n\n"
        "urlpatterns = [\n"
        "    path(\"login/\", views.login_view, name=\"login\"),\n"
        "    path(\"logout/\", views.logout_view, name=\"logout\"),\n"
        "    path(\"signup/\", views.signup_view, name=\"signup\"),\n"
        "]\n"
    )


def _auth_views(auth_framework: str) -> str:
    if auth_framework == "allauth":
        return (
            "from django.shortcuts import redirect\n\n"
            "def login_view(request):\n"
            "    return redirect(\"/accounts/login/\")\n\n"
            "def logout_view(request):\n"
            "    return redirect(\"/accounts/logout/\")\n\n"
            "def signup_view(request):\n"
            "    return redirect(\"/accounts/signup/\")\n"
        )
    return (
        "from django.contrib.auth import login, logout\n"
        "from django.contrib.auth.forms import AuthenticationForm\n"
        "from django.shortcuts import render, redirect\n"
        "from .forms import CustomUserCreationForm\n\n"
        "def login_view(request):\n"
        "    form = AuthenticationForm(request, data=request.POST or None)\n"
        "    if request.method == \"POST\" and form.is_valid():\n"
        "        login(request, form.get_user())\n"
        "        return redirect(\"auth:login\")\n"
        "    return render(request, \"authentication/login.html\", {\"form\": form})\n\n"
        "def logout_view(request):\n"
        "    logout(request)\n"
        "    return redirect(\"auth:login\")\n\n"
        "def signup_view(request):\n"
        "    form = CustomUserCreationForm(request.POST or None)\n"
        "    if request.method == \"POST\" and form.is_valid():\n"
        "        user = form.save()\n"
        "        login(request, user)\n"
        "        return redirect(\"auth:login\")\n"
        "    return render(request, \"authentication/signup.html\", {\"form\": form})\n"
    )


def _auth_forms() -> str:
    return (
        "from django.contrib.auth import get_user_model\n"
        "from django.contrib.auth.forms import UserCreationForm\n\n"
        "class CustomUserCreationForm(UserCreationForm):\n"
        "    class Meta(UserCreationForm.Meta):\n"
        "        model = get_user_model()\n"
        "        fields = (\"username\", \"email\")\n"
    )


def _auth_models_custom_user() -> str:
    return (
        "from django.contrib.auth.models import AbstractUser\n\n"
        "class CustomUser(AbstractUser):\n"
        "    pass\n"
    )


def _auth_base_template(css_framework: str) -> str:
    if css_framework == "tailwind":
        head_css = "<script src=\"https://cdn.tailwindcss.com\"></script>"
        body_cls = "bg-slate-100 text-slate-900 min-h-screen"
        header = (
            "<header class=\"bg-slate-900 text-white\">\n"
            "  <div class=\"max-w-3xl mx-auto px-4 py-3\">\n"
            "    <div class=\"text-lg font-semibold\">Django Manager</div>\n"
            "  </div>\n"
            "</header>\n"
        )
        main_open = "<main class=\"max-w-3xl mx-auto px-4 py-8\">"
    else:
        head_css = (
            "<link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css\" "
            "rel=\"stylesheet\">"
        )
        body_cls = "bg-light"
        header = (
            "<nav class=\"navbar navbar-dark bg-dark\">\n"
            "  <div class=\"container\">\n"
            "    <span class=\"navbar-brand mb-0 h1\">Django Manager</span>\n"
            "  </div>\n"
            "</nav>\n"
        )
        main_open = "<main class=\"container py-4\">"

    form_style = (
        "<style>\n"
        "form input, form select, form textarea {\n"
        "  width: 100%; padding: 0.5rem 0.75rem; margin-bottom: 0.75rem;\n"
        "  border: 1px solid #d1d5db; border-radius: 0.375rem;\n"
        "}\n"
        "form button { padding: 0.5rem 1rem; border-radius: 0.375rem; }\n"
        "</style>\n"
    )

    return (
        "<!doctype html>\n"
        "<html>\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        f"  {head_css}\n"
        f"  {form_style}\n"
        "  <title>Authentication</title>\n"
        "</head>\n"
        f"<body class=\"{body_cls}\">\n"
        f"{header}\n"
        f"{main_open}\n"
        "  {% block content %}{% endblock %}\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _auth_login_template(css_framework: str) -> str:
    card_open, card_close, btn_cls, link_cls = _auth_ui_classes(css_framework)
    return (
        "{% extends \"authentication/base.html\" %}\n"
        "{% block content %}\n"
        f"{card_open}\n"
        "<h2>Login</h2>\n"
        "<form method=\"post\">{% csrf_token %}{{ form.as_p }}\n"
        f"<button type=\"submit\" class=\"{btn_cls}\">Login</button></form>\n"
        f"<p class=\"mt-3\">No account? <a class=\"{link_cls}\" href=\"{{% url 'auth:signup' %}}\">Sign up</a></p>\n"
        f"{card_close}\n"
        "{% endblock %}\n"
    )


def _auth_signup_template(css_framework: str) -> str:
    card_open, card_close, btn_cls, link_cls = _auth_ui_classes(css_framework)
    return (
        "{% extends \"authentication/base.html\" %}\n"
        "{% block content %}\n"
        f"{card_open}\n"
        "<h2>Sign Up</h2>\n"
        "<form method=\"post\">{% csrf_token %}{{ form.as_p }}\n"
        f"<button type=\"submit\" class=\"{btn_cls}\">Create account</button></form>\n"
        f"<p class=\"mt-3\">Already have an account? <a class=\"{link_cls}\" href=\"{{% url 'auth:login' %}}\">Login</a></p>\n"
        f"{card_close}\n"
        "{% endblock %}\n"
    )


def _allauth_login_template(css_framework: str) -> str:
    card_open, card_close, btn_cls, link_cls = _auth_ui_classes(css_framework)
    return (
        "{% extends \"authentication/base.html\" %}\n"
        "{% block content %}\n"
        f"{card_open}\n"
        "<h2>Login</h2>\n"
        "<form method=\"post\">{% csrf_token %}{{ form.as_p }}\n"
        f"<button type=\"submit\" class=\"{btn_cls}\">Login</button></form>\n"
        f"<p class=\"mt-3\">No account? <a class=\"{link_cls}\" href=\"{{% url 'account_signup' %}}\">Sign up</a></p>\n"
        f"{card_close}\n"
        "{% endblock %}\n"
    )


def _allauth_signup_template(css_framework: str) -> str:
    card_open, card_close, btn_cls, link_cls = _auth_ui_classes(css_framework)
    return (
        "{% extends \"authentication/base.html\" %}\n"
        "{% block content %}\n"
        f"{card_open}\n"
        "<h2>Sign Up</h2>\n"
        "<form method=\"post\">{% csrf_token %}{{ form.as_p }}\n"
        f"<button type=\"submit\" class=\"{btn_cls}\">Create account</button></form>\n"
        f"<p class=\"mt-3\">Already have an account? <a class=\"{link_cls}\" href=\"{{% url 'account_login' %}}\">Login</a></p>\n"
        f"{card_close}\n"
        "{% endblock %}\n"
    )


def _allauth_logout_template(css_framework: str) -> str:
    card_open, card_close, btn_cls, _ = _auth_ui_classes(css_framework)
    return (
        "{% extends \"authentication/base.html\" %}\n"
        "{% block content %}\n"
        f"{card_open}\n"
        "<h2>Logout</h2>\n"
        "<form method=\"post\">{% csrf_token %}\n"
        f"<button type=\"submit\" class=\"{btn_cls}\">Logout</button></form>\n"
        f"{card_close}\n"
        "{% endblock %}\n"
    )


def _auth_ui_classes(css_framework: str) -> tuple[str, str, str, str]:
    if css_framework == "tailwind":
        card_open = "<div class=\"max-w-md mx-auto bg-white p-6 rounded shadow\">"
        card_close = "</div>"
        btn_cls = "px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700"
        link_cls = "text-emerald-700 hover:underline"
    else:
        card_open = "<div class=\"row justify-content-center\"><div class=\"col-md-6\"><div class=\"card shadow-sm\"><div class=\"card-body\">"
        card_close = "</div></div></div></div>"
        btn_cls = "btn btn-primary"
        link_cls = "link-primary"
    return card_open, card_close, btn_cls, link_cls


def _insert_list_entries(text: str, list_name: str, entries: list[str]) -> str:
    lines = text.splitlines()
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if start_idx is None and line.strip().startswith(f"{list_name}"):
            start_idx = i
            continue
        if start_idx is not None and "]" in line:
            end_idx = i
            break
    if start_idx is None or end_idx is None:
        return text

    # Determine indent from first list item or closing line
    indent = "    "
    for j in range(start_idx + 1, end_idx):
        if lines[j].strip():
            indent = lines[j][: len(lines[j]) - len(lines[j].lstrip())]
            break
    existing = "\n".join(lines[start_idx + 1 : end_idx])
    to_add = []
    for entry in entries:
        if entry in existing:
            continue
        if entry.startswith("path("):
            to_add.append(f"{indent}{entry},")
        else:
            to_add.append(f"{indent}\"{entry}\",")
    if not to_add:
        return text
    lines[end_idx:end_idx] = to_add
    return "\n".join(lines)


def _append_if_missing(text: str, snippet: str) -> str:
    if snippet.strip() in text:
        return text
    return text.rstrip() + "\n" + snippet


def _ensure_include_import(text: str) -> str:
    for i, line in enumerate(text.splitlines()):
        if line.startswith("from django.urls import"):
            if "include" in line:
                return text
            if line.endswith("path"):
                return text.replace(line, line + ", include")
            return text
    return "from django.urls import path, include\n" + text


def _base_template(css_framework: str, interactive: str) -> str:
    if css_framework == "tailwind":
        css = "<script src=\"https://cdn.tailwindcss.com\"></script>"
    elif css_framework == "bootstrap":
        css = (
            "<link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css\" "
            "rel=\"stylesheet\">"
        )
    else:
        css = ""
    if interactive == "jquery":
        js = (
            "<script src=\"https://code.jquery.com/jquery-3.7.1.min.js\"></script>\n"
            "<script src=\"/static/js/jquery.js\"></script>"
        )
    elif interactive == "ajax":
        js = "<script src=\"/static/js/ajax.js\"></script>"
    else:
        js = "<script src=\"https://unpkg.com/htmx.org@1.9.10\"></script>"
    return (
        "<!doctype html>\n"
        "<html>\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        f"  {css}\n"
        "</head>\n"
        "<body class=\"bg-light\">\n"
        "  <div class=\"container py-5\">\n"
        "    <h1>Django Manager</h1>\n"
        "    <p>Starter layout ready.</p>\n"
        "    {% block content %}{% endblock %}\n"
        "  </div>\n"
        f"  {js}\n"
        "</body>\n"
        "</html>\n"
    )


def _ajax_helper_js() -> str:
    return (
        "async function postJSON(url, data) {\n"
        "  const resp = await fetch(url, {\n"
        "    method: 'POST',\n"
        "    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },\n"
        "    body: JSON.stringify(data)\n"
        "  });\n"
        "  return await resp.json();\n"
        "}\n"
    )


def _jquery_helper_js() -> str:
    return (
        "function postJSON(url, data, cb) {\n"
        "  $.ajax({\n"
        "    url: url,\n"
        "    method: 'POST',\n"
        "    contentType: 'application/json',\n"
        "    data: JSON.stringify(data),\n"
        "    success: cb,\n"
        "  });\n"
        "}\n"
    )


def _skeleton_urls() -> str:
    return (
        "from django.urls import path\n"
        "from . import views\n\n"
        "urlpatterns = [\n"
        "    path(\"\", views.home, name=\"home\"),\n"
        "]\n"
    )


def _skeleton_views() -> str:
    return (
        "from django import get_version\n"
        "from django.shortcuts import render\n\n"
        "def home(request):\n"
        "    return render(request, \"skeleton/home.html\", {\"django_version\": get_version()})\n"
    )


def _skeleton_home_template(css_framework: str) -> str:
    return (
        "{% extends \"base.html\" %}\n"
        "{% block content %}\n"
        "<style>\n"
        "  :root { --bg: #0a0a0a; --glow: #3ddc97; --text: #e5f7ef; }\n"
        "  body { background: radial-gradient(1200px circle at 10% 10%, #0f2a1d 0%, #0a0a0a 45%), #0a0a0a; }\n"
        "  .dm-wrap { min-height: 70vh; display: grid; place-items: center; }\n"
        "  .dm-title {\n"
        "    font-family: \"Segoe UI\", system-ui, sans-serif;\n"
        "    font-size: clamp(2.5rem, 6vw, 4.5rem);\n"
        "    letter-spacing: 0.2rem; text-transform: uppercase;\n"
        "    color: var(--text); position: relative;\n"
        "    animation: fadeUp 1.1s ease-out both;\n"
        "    text-shadow: 0 0 24px rgba(61, 220, 151, 0.35);\n"
        "  }\n"
        "  .dm-title::after {\n"
        "    content: \"\"; display: block; height: 2px; width: 100%;\n"
        "    margin-top: 16px; background: linear-gradient(90deg, transparent, var(--glow), transparent);\n"
        "    opacity: 0.7; animation: glowPulse 2.4s ease-in-out infinite;\n"
        "  }\n"
        "  @keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }\n"
        "  @keyframes glowPulse { 0%,100% { opacity: .4; } 50% { opacity: .9; } }\n"
        "</style>\n"
        "<div class=\"dm-wrap\">\n"
        "  <div class=\"dm-title\">DJango Manager</div>\n"
        "</div>\n"
        "{% endblock %}\n"
    )


def ensure_pyproject(cfg: ProjectConfig) -> None:
    pyproject = cfg.path / "pyproject.toml"
    if pyproject.exists():
        return
    text = (
        "[build-system]\n"
        "requires = [\"hatchling\"]\n"
        "build-backend = \"hatchling.build\"\n"
        "\n"
        "[project]\n"
        f"name = \"{cfg.name}\"\n"
        "version = \"0.1.0\"\n"
        f"description = \"{cfg.name} Django project\"\n"
        f"requires-python = \">={cfg.python_ver}\"\n"
    )
    pyproject.write_text(text, encoding="utf-8")


def _venv_env(cfg: ProjectConfig) -> dict:
    """Build an env dict that points PATH at the venv binaries."""
    return venv_env_from_path(cfg.venv_path)


def venv_env_from_path(venv_path: Path) -> dict:
    env = os.environ.copy()
    bin_dir = venv_path / ("Scripts" if os.name == "nt" else "bin")
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = str(venv_path)
    env.pop("PYTHONHOME", None)
    return env


def _python_bin(project_path: Path, venv_path: Optional[Path] = None) -> Path:
    venv = venv_path if venv_path else (project_path / ".venv")
    if os.name == "nt":
        candidate = venv / "Scripts" / "python.exe"
    else:
        candidate = venv / "bin" / "python"
    if candidate.exists():
        return candidate
    return Path(sys.executable)


def venv_python(venv_path: Path) -> Path:
    if os.name == "nt":
        candidate = venv_path / "Scripts" / "python.exe"
    else:
        candidate = venv_path / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def _venv_bin(venv_path: Path, name: str) -> Optional[Path]:
    if os.name == "nt":
        candidate = venv_path / "Scripts" / f"{name}.exe"
    else:
        candidate = venv_path / "bin" / name
    return candidate if candidate.exists() else None


def _venv_has_module(venv_path: Path, module: str) -> bool:
    win_path = venv_path / "Lib" / "site-packages" / module
    if win_path.exists():
        return True
    for candidate in venv_path.glob(f"lib/python*/site-packages/{module}"):
        if candidate.exists():
            return True
    return False


def _pip_install_uv(python_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(python_path), "-m", "pip", "install", "uv"],
        capture_output=True,
        text=True,
    )


def get_python_version(venv_path: Path) -> Optional[str]:
    uv = shutil.which("uv")
    candidates = []
    if uv:
        candidates.append([uv, "run", "--python", str(venv_python(venv_path)), "python", "--version"])
    candidates.append([str(venv_python(venv_path)), "--version"])
    for cmd in candidates:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except Exception:
            continue
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0 or not output:
            continue
        if output.lower().startswith("python"):
            parts = output.split()
            if len(parts) >= 2:
                return parts[1].strip()
    return None


def get_package_version(venv_path: Path, package: str) -> Optional[str]:
    try:
        result = subprocess.run(
            [str(venv_python(venv_path)), "-m", "pip", "show", package],
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in (result.stdout or "").splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None


def list_installed_packages(venv_path: Path) -> list[str]:
    try:
        result = subprocess.run(
            [str(venv_python(venv_path)), "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    pkgs: list[str] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        name = line.split("==", 1)[0]
        pkgs.append(name)
    return pkgs


def pip_uninstall_packages(venv_path: Path, packages: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(venv_python(venv_path)), "-m", "pip", "uninstall", "-y", *packages],
        capture_output=True,
        text=True,
    )
