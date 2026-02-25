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
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Optional


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

    @property
    def path(self) -> Path:
        return self.location / self.name

    @property
    def venv_path(self) -> Path:
        return self.path / ".venv"

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
        _ensure_pyproject(cfg)
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
) -> AsyncGenerator[str, None]:
    """
    Stream output lines from: python manage.py <command> [args]
    """
    venv_python = _python_bin(project_path)
    manage_py   = project_path / "manage.py"

    proc = await asyncio.create_subprocess_exec(
        str(venv_python), str(manage_py), command, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=project_path,
    )

    async for line in proc.stdout:
        yield line.decode("utf-8", errors="replace").rstrip("\n")

    await proc.wait()


async def start_runserver(
    project_path: Path,
    port: int = 8000,
) -> asyncio.subprocess.Process:
    """
    Start `python manage.py runserver` as a long-running process.
    Caller is responsible for streaming proc.stdout and calling proc.terminate().
    """
    venv_python = _python_bin(project_path)
    manage_py   = project_path / "manage.py"

    proc = await asyncio.create_subprocess_exec(
        str(venv_python), str(manage_py), "runserver", f"0.0.0.0:{port}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=project_path,
    )
    return proc


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


def _ensure_pyproject(cfg: ProjectConfig) -> None:
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
    env = os.environ.copy()
    bin_dir = cfg.venv_path / ("Scripts" if os.name == "nt" else "bin")
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = str(cfg.venv_path)
    env.pop("PYTHONHOME", None)
    return env


def _python_bin(project_path: Path) -> Path:
    venv = project_path / ".venv"
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"
