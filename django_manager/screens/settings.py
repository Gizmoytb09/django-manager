"""
Django Manager — Settings Screen
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Static

from ..core.settings import AppSettings, load_settings, save_settings


class SettingsScreen(Screen):
    CSS = """
    SettingsScreen {
        align: center middle;
        background: #0a0a0a;
    }

    #settings-wrap {
        width: 64;
        height: auto;
        background: #111111;
        border: tall #1a1a1a;
        padding: 2 3;
    }

    #st-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    .st-section { color: #555555; margin: 1 0 1 0; }
    .st-row { height: 3; align: center middle; margin-bottom: 1; }

    .btn-toggle {
        height: 3;
        padding: 0 2;
        margin: 0 1;
        background: #111111;
        color: #555555;
        border: tall #1a1a1a;
        content-align: center middle;
        min-width: 18;
    }
    .btn-toggle--active {
        background: #0a1f14;
        color: #44B78B;
        border: tall #092E20;
        text-style: bold;
    }

    #settings-actions { height: 3; margin-top: 2; align: center middle; }
    #btn-close {
        width: 24;
        background: #092E20;
        color: #44B78B;
        border: tall #44B78B;
        text-style: bold;
        content-align: center middle;
    }
    #btn-close:hover { background: #0d3d28; border: tall #6ddba8; color: #6ddba8; }
    """

    layout_mode: reactive[str] = reactive("split")
    sidebar_compact: reactive[bool] = reactive(False)
    auto_switch_command: reactive[bool] = reactive(True)
    show_project_path: reactive[bool] = reactive(True)
    show_server_timestamps: reactive[bool] = reactive(True)
    show_server_levels: reactive[bool] = reactive(True)
    show_running_badge: reactive[bool] = reactive(True)
    show_command_welcome: reactive[bool] = reactive(True)
    server_auto_scroll: reactive[bool] = reactive(True)
    command_auto_scroll: reactive[bool] = reactive(True)

    def compose(self) -> ComposeResult:
        with Container(id="settings-wrap"):
            yield Static("Settings", id="st-title")

            yield Static("Layout Preference", classes="st-section")
            with Horizontal(classes="st-row"):
                yield Button("Split (default)", id="layout-split", classes="btn-toggle")
                yield Button("Tabs", id="layout-tabs", classes="btn-toggle")

            yield Static("Sidebar Density", classes="st-section")
            with Horizontal(classes="st-row"):
                yield Button("Compact Sidebar", id="toggle-sidebar", classes="btn-toggle")

            yield Static("Command Behavior", classes="st-section")
            with Horizontal(classes="st-row"):
                yield Button("Auto-switch to Command", id="toggle-auto-cmd", classes="btn-toggle")

            yield Static("Header", classes="st-section")
            with Horizontal(classes="st-row"):
                yield Button("Show Project Path", id="toggle-path", classes="btn-toggle")

            yield Static("Command Output", classes="st-section")
            with Horizontal(classes="st-row"):
                yield Button("Show Welcome Hint", id="toggle-cmd-welcome", classes="btn-toggle")
                yield Button("Auto-scroll Command", id="toggle-cmd-scroll", classes="btn-toggle")

            yield Static("Server Output", classes="st-section")
            with Horizontal(classes="st-row"):
                yield Button("Show Timestamps", id="toggle-ts", classes="btn-toggle")
                yield Button("Show Levels", id="toggle-levels", classes="btn-toggle")
            with Horizontal(classes="st-row"):
                yield Button("Show RUNNING Badge", id="toggle-badge", classes="btn-toggle")
                yield Button("Auto-scroll Server", id="toggle-srv-scroll", classes="btn-toggle")

            with Horizontal(id="settings-actions"):
                yield Button("Close", id="btn-close")

    def on_mount(self) -> None:
        self._apply_responsive()
        settings = load_settings()
        self.layout_mode = settings.layout_mode
        self.sidebar_compact = settings.sidebar_compact
        self.auto_switch_command = settings.auto_switch_command
        self.show_project_path = settings.show_project_path
        self.show_server_timestamps = settings.show_server_timestamps
        self.show_server_levels = settings.show_server_levels
        self.show_running_badge = settings.show_running_badge
        self.show_command_welcome = settings.show_command_welcome
        self.server_auto_scroll = settings.server_auto_scroll
        self.command_auto_scroll = settings.command_auto_scroll
        self._sync_buttons()

    def on_resize(self, event) -> None:  # type: ignore[override]
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        wrap = self.query_one("#settings-wrap")
        width = max(56, min(self.size.width - 6, 90))
        wrap.styles.width = width

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "layout-split":
                self.layout_mode = "split"
            case "layout-tabs":
                self.layout_mode = "tabs"
            case "toggle-sidebar":
                self.sidebar_compact = not self.sidebar_compact
            case "toggle-auto-cmd":
                self.auto_switch_command = not self.auto_switch_command
            case "toggle-path":
                self.show_project_path = not self.show_project_path
            case "toggle-cmd-welcome":
                self.show_command_welcome = not self.show_command_welcome
            case "toggle-cmd-scroll":
                self.command_auto_scroll = not self.command_auto_scroll
            case "toggle-ts":
                self.show_server_timestamps = not self.show_server_timestamps
            case "toggle-levels":
                self.show_server_levels = not self.show_server_levels
            case "toggle-badge":
                self.show_running_badge = not self.show_running_badge
            case "toggle-srv-scroll":
                self.server_auto_scroll = not self.server_auto_scroll
            case "btn-close":
                self.app.pop_screen()
                return
        self._save()
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self._set_active("layout-split", self.layout_mode == "split")
        self._set_active("layout-tabs", self.layout_mode == "tabs")
        self._set_active("toggle-sidebar", self.sidebar_compact)
        self._set_active("toggle-auto-cmd", self.auto_switch_command)
        self._set_active("toggle-path", self.show_project_path)
        self._set_active("toggle-cmd-welcome", self.show_command_welcome)
        self._set_active("toggle-cmd-scroll", self.command_auto_scroll)
        self._set_active("toggle-ts", self.show_server_timestamps)
        self._set_active("toggle-levels", self.show_server_levels)
        self._set_active("toggle-badge", self.show_running_badge)
        self._set_active("toggle-srv-scroll", self.server_auto_scroll)

    def _set_active(self, button_id: str, active: bool) -> None:
        btn = self.query_one(f"#{button_id}", Button)
        if active:
            btn.add_class("btn-toggle--active")
        else:
            btn.remove_class("btn-toggle--active")

    def _save(self) -> None:
        settings = AppSettings(
            layout_mode=self.layout_mode,
            sidebar_compact=self.sidebar_compact,
            auto_switch_command=self.auto_switch_command,
            show_project_path=self.show_project_path,
            show_server_timestamps=self.show_server_timestamps,
            show_server_levels=self.show_server_levels,
            show_running_badge=self.show_running_badge,
            show_command_welcome=self.show_command_welcome,
            server_auto_scroll=self.server_auto_scroll,
            command_auto_scroll=self.command_auto_scroll,
        )
        save_settings(settings)
