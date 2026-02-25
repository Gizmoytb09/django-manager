import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from django_manager.core.operations import _combined_output, _ensure_pyproject, _run, uv_available, uv_path


class TestUvAddDjango(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("DJM_RUN_UV_INTEGRATION") == "1",
        "Set DJM_RUN_UV_INTEGRATION=1 to run uv integration test",
    )
    def test_uv_add_django(self) -> None:
        uv = os.environ.get("DJM_UV_PATH")
        if not uv:
            if not uv_available():
                self.skipTest("uv not installed on PATH and DJM_UV_PATH not set")
            uv = uv_path()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            venv_path = tmp_path / ".venv"

            result = asyncio.run(
                _run([uv, "venv", "--python", "3.12", str(venv_path)], cwd=tmp_path)
            )
            self.assertEqual(
                result.returncode,
                0,
                msg="uv venv failed:\n" + (_combined_output(result) or "<no output>"),
            )

            env = os.environ.copy()
            bin_dir = venv_path / ("Scripts" if os.name == "nt" else "bin")
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            env["VIRTUAL_ENV"] = str(venv_path)
            env.pop("PYTHONHOME", None)

            class _Cfg:
                name = "tmp_project"
                path = tmp_path
                python_ver = "3.12"

            _ensure_pyproject(_Cfg)
            pkg_dir = tmp_path / "tmp_project"
            pkg_dir.mkdir(exist_ok=True)
            (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

            result = asyncio.run(
                _run([uv, "add", "django==5.2"], cwd=tmp_path, env=env)
            )
            self.assertEqual(
                result.returncode,
                0,
                msg="uv add failed:\n" + (_combined_output(result) or "<no output>"),
            )
