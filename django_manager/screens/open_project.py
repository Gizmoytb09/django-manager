"""
Django Manager — Open Existing Project
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, DirectoryTree, Input, Static

from ..core.operations import (
    ProjectConfig,
    get_package_version,
    get_python_version,
    list_installed_packages,
)


class OpenProjectScreen(Screen):
    CSS = """
    OpenProjectScreen {
        align: center middle;
        background: #0a0a0a;
    }

    #open-wrap {
        width: 80;
        height: auto;
        background: #111111;
        border: tall #1a1a1a;
        padding: 2 3;
    }

    #open-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #open-sub   { color: #555555; margin-bottom: 1; }
    #open-search {
        background: #0a0a0a;
        border: tall #1a1a1a;
        padding: 0 1;
        height: 3;
        margin-bottom: 1;
    }
    #open-search:focus { border: tall #44B78B; }
    #open-tree {
        background: #0a0a0a;
        border: tall #1a1a1a;
        height: 16;
        margin-bottom: 1;
    }
    #open-selected { color: #3a3a3a; height: auto; }
    #open-venv     { color: #3a3a3a; height: auto; margin-bottom: 1; }
    #open-error { color: #e06c75; height: auto; margin-top: 1; }

    #open-actions { height: 3; margin-top: 1; align: center middle; }
    #btn-open {
        width: 18;
        background: #092E20;
        color: #44B78B;
        border: tall #44B78B;
        text-style: bold;
        content-align: center middle;
        padding: 0 2;
        margin-right: 2;
    }
    #btn-open:hover { background: #0d3d28; border: tall #6ddba8; color: #6ddba8; }

    #btn-cancel {
        width: 18;
        background: #111111;
        color: #888888;
        border: tall #1a1a1a;
        content-align: center middle;
        padding: 0 2;
    }
    #btn-cancel:hover { background: #151515; border: tall #2a2a2a; color: #aaaaaa; }
    """

    selected_manage: reactive[Optional[Path]] = reactive(None)
    selected_venv: reactive[Optional[Path]] = reactive(None)
    venv_ready: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        with Container(id="open-wrap"):
            yield Static("Open Existing Project", id="open-title")
            yield Static("Select the project's manage.py file.", id="open-sub")
            yield Input(placeholder="Search (type to jump)", id="open-search")
            yield DirectoryTree(Path.home(), id="open-tree")
            yield Static("Selected: (none)", id="open-selected")
            yield Static("Venv: (not selected)", id="open-venv")
            yield Static("", id="open-error")
            with Horizontal(id="open-actions"):
                yield Button("Open", id="btn-open")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        self._apply_responsive()
        self.query_one("#open-tree", DirectoryTree).focus()

    def on_resize(self, event) -> None:  # type: ignore[override]
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        wrap = self.query_one("#open-wrap")
        width = max(60, min(self.size.width - 6, 110))
        wrap.styles.width = width
        tree = self.query_one("#open-tree")
        tree.styles.height = max(10, min(self.size.height - 10, 30))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-open":
                self._open()
            case "btn-cancel":
                self.app.pop_screen()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "open-search":
            self._search_tree(event.value)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        if _is_venv_dir(event.path):
            self.selected_venv = event.path
            self._set_error("")
            return
        self._set_error("Select manage.py (not just the folder).")
        event.node.expand()
        self._select_manage_py(event.node, attempts=6)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        if event.path.name.lower() == "manage.py":
            self.selected_manage = event.path
        else:
            self._set_error("Select manage.py (not other files).")

    def watch_selected_manage(self, val: Optional[Path]) -> None:
        label = self.query_one("#open-selected", Static)
        if val is None:
            label.update("Selected: (none)")
        else:
            label.update(f"Selected: {val}")
            if self.selected_venv is None:
                self.selected_venv = _detect_venv_upwards(val.parent)
        self._set_error("")

    def watch_selected_venv(self, val: Optional[Path]) -> None:
        label = self.query_one("#open-venv", Static)
        if val is None:
            label.update("Venv: (not selected)")
            if self.selected_manage is not None:
                self._set_error("Select a virtual environment folder (contains pyvenv.cfg).")
            self.venv_ready = False
        else:
            ok = _venv_has_django(val)
            status = "Django OK" if ok else "Django missing"
            label.update(f"Venv: {val} ({status})")
            self.venv_ready = ok
            if ok:
                self._set_error("")
            else:
                self._set_error("Django is not installed in this venv. Install it and try again.")

    def _open(self) -> None:
        if not self.selected_manage:
            self._set_error("Select manage.py to open the project.")
            return
        root = self._resolve_project_root(self.selected_manage)
        if not root:
            self._set_error("Path must contain manage.py (project root).")
            return
        if not self.selected_venv:
            self._set_error("Select a virtual environment folder (contains pyvenv.cfg).")
            return
        if not self.venv_ready:
            self._set_error("Django is not installed in the selected venv.")
            return
        cfg = self._build_config(root)
        from .dashboard import DashboardScreen
        self.app.switch_screen(DashboardScreen(cfg=cfg))

    def _search_tree(self, query: str) -> None:
        query = query.strip().lower()
        if not query:
            return
        tree = self.query_one("#open-tree", DirectoryTree)
        for line in tree._tree_lines:
            node = line.node
            data = node.data
            label = data.path.name if data and hasattr(data, "path") else (
                node.label.plain if hasattr(node.label, "plain") else str(node.label)
            )
            if label.lower().startswith(query):
                tree.select_node(node)
                tree.scroll_to_node(node, animate=False)
                return

    def _select_manage_py(self, node, attempts: int = 4) -> None:
        tree = self.query_one("#open-tree", DirectoryTree)
        base = node.data.path if node.data and hasattr(node.data, "path") else None
        # 1) Check direct children
        for child in node.children:
            data = child.data
            if data and data.path.name.lower() == "manage.py":
                tree.select_node(child)
                tree.scroll_to_node(child, animate=False)
                self._set_error("")
                return
        # 2) Check loaded nodes under this folder
        if base:
            for line in tree._tree_lines:
                data = line.node.data
                if not data or not hasattr(data, "path"):
                    continue
                if data.path.name.lower() != "manage.py":
                    continue
                try:
                    if data.path.is_relative_to(base):
                        tree.select_node(line.node)
                        tree.scroll_to_node(line.node, animate=False)
                        self._set_error("")
                        return
                except Exception:
                    pass
        # 3) Retry after load
        if attempts > 0:
            self.set_timer(0.08, lambda: self._select_manage_py(node, attempts - 1))

    def _set_error(self, msg: str) -> None:
        self.query_one("#open-error", Static).update(msg)

    def _resolve_project_root(self, path: Path) -> Optional[Path]:
        if path.is_file():
            if path.name.lower() != "manage.py":
                return None
            root = path.parent
        else:
            root = path
        if not root.exists():
            return None
        if not (root / "manage.py").exists():
            return None
        return root

    def _build_config(self, root: Path) -> ProjectConfig:
        name = root.name
        location = root.parent
        packages, python_req, django_ver = self._read_project_metadata(root, self.selected_venv)
        return ProjectConfig(
            name=name,
            location=location,
            python_ver=python_req or "unknown",
            django_ver=django_ver or "unknown",
            starter_pack="existing",
            packages=packages,
            venv_dir=self.selected_venv,
        )

    def _read_project_metadata(
        self, root: Path, venv_path: Optional[Path]
    ) -> Tuple[list[str], Optional[str], Optional[str]]:
        if not venv_path:
            return [], None, None
        python_ver = get_python_version(venv_path)
        django_ver = get_package_version(venv_path, "django")
        packages = list_installed_packages(venv_path)
        return packages, python_ver, django_ver


def _is_venv_dir(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    if (path / "pyvenv.cfg").exists():
        return True
    if (path / "Scripts" / "python.exe").exists():
        return True
    if (path / "bin" / "python").exists():
        return True
    return False


def _detect_venv_upwards(start: Path, max_depth: int = 3) -> Optional[Path]:
    cur = start
    for _ in range(max_depth + 1):
        if _is_venv_dir(cur):
            return cur
        for name in (".venv", "venv", "env", ".env"):
            candidate = cur / name
            if _is_venv_dir(candidate):
                return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _venv_has_django(venv_path: Path) -> bool:
    if not venv_path.exists():
        return False
    win_path = venv_path / "Lib" / "site-packages" / "django" / "__init__.py"
    if win_path.exists():
        return True
    for candidate in venv_path.glob("lib/python*/site-packages/django/__init__.py"):
        if candidate.exists():
            return True
    return False
