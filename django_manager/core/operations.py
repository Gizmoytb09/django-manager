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
    return shutil.which("uv") is not None


def uv_path() -> str:
    path = shutil.which("uv")
    if not path:
        raise FileNotFoundError(
            "uv not found. Install via: curl -LsSf https://astral.sh/uv/install.sh | sh"
        )
    return path


# ── Project creation — async step generator ─────────────────────────────────

async def create_project(
    cfg: ProjectConfig,
) -> AsyncGenerator[tuple[str, StepResult], None]:
    """
    Yields (step_id, StepResult) tuples as each step completes.
    Steps: mkdir, venv, activate, install, startproject, lockfile
    """
    uv = uv_path()

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
        [uv, "venv", "--python", cfg.python_ver, str(cfg.venv_path)],
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
        [uv, "pip", "install", f"django=={cfg.django_ver}"],
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
        [uv, "add", *packages],
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

    result = await _run([uv, "lock"], cwd=cfg.path, env=_venv_env(cfg))
    yield "lockfile", StepResult(
        ok=result.returncode == 0,
        message="pyproject.toml + uv.lock generated" if result.returncode == 0 else "Lock generation failed",
        detail=_combined_output(result),
    )


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
    uv = uv_path()
    env = venv_env_from_path(venv_path) if venv_path else None
    return await _run([uv, "add", *packages], cwd=project_path, env=env)


async def uv_remove_packages(
    project_path: Path,
    packages: list[str],
    venv_path: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    uv = uv_path()
    env = venv_env_from_path(venv_path) if venv_path else None
    return await _run([uv, "remove", *packages], cwd=project_path, env=env)


async def uv_list_packages(
    project_path: Path,
    venv_path: Optional[Path] = None,
) -> list[str]:
    uv = uv_path()
    env = venv_env_from_path(venv_path) if venv_path else None
    result = await _run([uv, "pip", "list", "--format=freeze"], cwd=project_path, env=env)
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
