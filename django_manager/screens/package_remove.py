"""
Django Manager — Remove Packages (TUI)
"""
from __future__ import annotations

import re
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Static

from ..core.operations import (
    ProjectConfig,
    pip_uninstall_packages,
    read_project_dependencies,
    uv_list_packages,
    uv_remove_packages,
)


class PackageRemoveScreen(Screen):
    CSS = """
    PackageRemoveScreen {
        align: center middle;
        background: #0a0a0a;
    }

    #pr-wrap {
        width: 72;
        height: auto;
        background: #111111;
        border: tall #1a1a1a;
        padding: 2 3;
    }

    #pr-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #pr-sub   { color: #555555; margin-bottom: 1; }

    #pr-scroll {
        height: 14;
        background: #0a0a0a;
        border: tall #1a1a1a;
        padding: 1 2;
        margin-bottom: 1;
    }

    #pr-status { color: #3a3a3a; height: auto; margin-bottom: 1; }
    #pr-error  { color: #e06c75; height: auto; }

    #pr-actions { height: 3; margin-top: 1; align: center middle; }
    #btn-remove {
        width: 18;
        background: #092E20;
        color: #44B78B;
        border: tall #44B78B;
        text-style: bold;
        content-align: center middle;
        margin-right: 2;
        padding: 0 2;
    }
    #btn-remove:hover { background: #0d3d28; border: tall #6ddba8; color: #6ddba8; }

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

    packages: reactive[list[str]] = reactive(list)
    busy: reactive[bool] = reactive(False)
    _loading: reactive[bool] = reactive(False)

    def __init__(self, cfg: ProjectConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        with Container(id="pr-wrap"):
            yield Static("Remove Packages", id="pr-title")
            yield Static("Select packages to remove from this project.", id="pr-sub")
            with ScrollableContainer(id="pr-scroll"):
                yield Static("Loading packages...", id="pr-loading")
            yield Static("", id="pr-status")
            yield Static("", id="pr-error")
            with Horizontal(id="pr-actions"):
                yield Button("Remove", id="btn-remove")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        self._apply_responsive()
        self.run_worker(self._load_packages())

    def on_resize(self, event) -> None:  # type: ignore[override]
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        wrap = self.query_one("#pr-wrap")
        width = max(56, min(self.size.width - 6, 96))
        wrap.styles.width = width
        scroll = self.query_one("#pr-scroll")
        scroll.styles.height = max(10, min(self.size.height - 12, 24))

    async def _load_packages(self) -> None:
        if self._loading:
            return
        self._loading = True
        try:
            self._set_error("")
            try:
                pkgs = await uv_list_packages(self.cfg.path, venv_path=self.cfg.venv_path)
            except FileNotFoundError as e:
                self._set_error(str(e))
                pkgs = read_project_dependencies(self.cfg.path)

            normalized = []
            for raw in pkgs:
                name = _normalize_dep_name(raw)
                if name:
                    normalized.append(name)
            self.packages = sorted(set(normalized))
            self._render_packages()
        finally:
            self._loading = False

    def _render_packages(self) -> None:
        scroll = self.query_one("#pr-scroll", ScrollableContainer)
        scroll.remove_children()
        if not self.packages:
            scroll.mount(Static("No packages found.", id="pr-empty"))
            return
        for pkg in self.packages:
            scroll.mount(Checkbox(pkg))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-remove":
                self._remove_selected()
            case "btn-cancel":
                self.app.pop_screen()

    def _remove_selected(self) -> None:
        if self.busy:
            return
        selected = self._get_selected_packages()
        if not selected:
            self._set_error("Select at least one package.")
            return
        self.run_worker(self._remove_packages(selected))

    def _get_selected_packages(self) -> list[str]:
        selected: list[str] = []
        for checkbox in self.query(Checkbox):
            if checkbox.value:
                selected.append(checkbox.label.plain)
        return selected

    async def _remove_packages(self, packages: list[str]) -> None:
        self.busy = True
        self._set_error("")
        self.query_one("#pr-status", Static).update("Removing packages...")
        self._set_buttons_enabled(False)
        try:
            result = await uv_remove_packages(
                self.cfg.path, packages, venv_path=self.cfg.venv_path
            )
        except FileNotFoundError as e:
            self._set_error(str(e))
            self.query_one("#pr-status", Static).update("")
            self._set_buttons_enabled(True)
            self.busy = False
            return

        if result.returncode != 0 and "pyproject.toml" in (result.stderr or ""):
            if self.cfg.venv_path.exists():
                result = pip_uninstall_packages(self.cfg.venv_path, packages)

        if result.returncode == 0:
            self.query_one("#pr-status", Static).update(f"Removed: {', '.join(packages)}")
        else:
            output = (result.stderr or result.stdout or "").strip()
            self._set_error(output or "Remove failed.")
            self.query_one("#pr-status", Static).update("")

        self._set_buttons_enabled(True)
        self.busy = False
        await self._load_packages()

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.query_one("#btn-remove", Button).disabled = not enabled
        self.query_one("#btn-cancel", Button).disabled = not enabled

    def _set_error(self, msg: str) -> None:
        self.query_one("#pr-error", Static).update(msg)


def _normalize_dep_name(dep: str) -> str:
    dep = dep.strip()
    if not dep:
        return ""
    parts = re.split(r"[<>=!~\\s;\\[]", dep, maxsplit=1)
    return parts[0].strip()
