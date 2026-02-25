"""
Django Manager — Project Dashboard
Layout: header | sidebar | [server panel / command output / input bar]
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.message import Message
from textual.widgets import Button, Input, Label, Static

from ..core.operations import ProjectConfig, run_django_command, start_runserver

# ── Rich markup helpers ──────────────────────────────────────────────────────

def _badge(text: str, kind: str = "ok") -> str:
    colors = {
        "ok":      ("#44B78B", "#0a1f14", "#092E20"),
        "err":     ("#e06c75", "#1f0d0d", "#3a1a1a"),
        "info":    ("#61afef", "#0d1f2d", "#1a3a50"),
        "warn":    ("#e5c07b", "#1f1a0d", "#3a2e1a"),
        "neutral": ("#888888", "#111111", "#1a1a1a"),
    }
    fg, bg, bd = colors.get(kind, colors["neutral"])
    return f"[bold {fg} on {bg}] {text} [/]"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── Sidebar items ────────────────────────────────────────────────────────────

SIDEBAR_ITEMS = [
    ("DJANGO", [
        ("▶", "Runserver"),
        ("⟳", "Migrate"),
        ("+", "Makemigrations"),
        ("◎", "Shell"),
        ("✦", "Collectstatic"),
    ]),
    ("PROJECT", [
        ("📦", "Packages"),
        ("⚙",  "Settings"),
        ("📱", "Apps"),
    ]),
    ("MANAGER", [
        ("◉", "Docs"),
        ("+", "Add Package"),
        ("↑", "Update Deps"),
        ("🔒", "Lock File"),
    ]),
]


class Sidebar(Vertical):
    DEFAULT_CSS = """
    Sidebar {
        width: 22;
        background: #0f0f0f;
        border-right: tall #1a1a1a;
        padding: 1 0;
    }
    .sb-section {
        color: #1e6e42;
        padding: 1 2 0 2;
        height: 2;
        text-style: bold;
    }
    .sb-item {
        height: 3;
        padding: 0 2;
        color: #3a3a3a;
        border: tall transparent;
        align: left middle;
    }
    .sb-item:hover  { background: #111111; color: #888888; }
    .sb-item--active {
        background: #0a1f14; color: #44B78B;
        border: tall #092E20;
    }
    .sb-icon { width: 3; }
    """

    active_item: reactive[str] = reactive("Runserver")

    def compose(self) -> ComposeResult:
        for section, items in SIDEBAR_ITEMS:
            yield Static(section, classes="sb-section")
            for icon, name in items:
                yield Static(
                    f" {icon}  {name}",
                    id=f"sb-{name.lower().replace(' ', '-')}",
                    classes="sb-item" + (" sb-item--active" if name == "Runserver" else ""),
                )

    def on_click(self, event) -> None:
        for section, items in SIDEBAR_ITEMS:
            for icon, name in items:
                item_id = f"sb-{name.lower().replace(' ', '-')}"
                el = self.query_one(f"#{item_id}", Static)
                if event.widget is el:
                    self.active_item = name
                    break

    def watch_active_item(self, val: str) -> None:
        for section, items in SIDEBAR_ITEMS:
            for icon, name in items:
                item_id = f"sb-{name.lower().replace(' ', '-')}"
                el = self.query_one(f"#{item_id}", Static)
                if name == val:
                    el.add_class("sb-item--active")
                else:
                    el.remove_class("sb-item--active")


# ── Server output panel ──────────────────────────────────────────────────────

class ServerPanel(Vertical):
    DEFAULT_CSS = """
    ServerPanel {
        height: 16;
        border-bottom: tall #1a1a1a;
    }
    #srv-header {
        height: 3;
        background: #0f0f0f;
        border-bottom: tall #1a1a1a;
        padding: 0 2;
        align: left middle;
    }
    #srv-title { color: #3a3a3a; text-style: bold; width: 1fr; }
    #srv-scroll { height: 1fr; background: #0a0a0a; padding: 0 1; }
    .srv-line  { height: 2; align: left middle; padding: 0 1; }
    .srv-time  { color: #1e1e1e; width: 10; }
    .srv-level { width: 8; }
    .srv-msg   { width: 1fr; color: #555555; }
    .srv-lv-ok   { color: #44B78B; }
    .srv-lv-info { color: #61afef; }
    .srv-lv-warn { color: #e5c07b; }
    .srv-lv-err  { color: #e06c75; }
    """

    running: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        with Horizontal(id="srv-header"):
            yield Static("SERVER OUTPUT", id="srv-title")
            yield Button("▶ Start", id="btn-srv-start", classes="btn-action-green")
            yield Button("⟳",      id="btn-srv-restart", classes="btn-action")
            yield Button("■ Stop",  id="btn-srv-stop",    classes="btn-action-red")
        with ScrollableContainer(id="srv-scroll"):
            yield Static(
                "[#1e1e1e]  Server not running — press Start or type: django runserver[/]",
                id="srv-placeholder",
                markup=True,
            )

    def on_mount(self) -> None:
        self.query_one("#btn-srv-stop").display   = False
        self.query_one("#btn-srv-restart").display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-srv-start":   self.post_message(self.StartServer())
            case "btn-srv-stop":    self.post_message(self.StopServer())
            case "btn-srv-restart": self.post_message(self.RestartServer())

    def append_line(self, time: str, level: str, msg: str) -> None:
        lvl_cls = {
            "OK": "srv-lv-ok", "INFO": "srv-lv-info",
            "WARN": "srv-lv-warn", "ERROR": "srv-lv-err",
        }.get(level.upper(), "srv-lv-info")
        scroll = self.query_one("#srv-scroll", ScrollableContainer)
        # Remove placeholder
        try:
            scroll.query_one("#srv-placeholder").remove()
        except Exception:
            pass
        line = Horizontal(classes="srv-line")
        line.compose_add_child(Static(time,  classes="srv-time"))
        line.compose_add_child(Static(level, classes=f"srv-level {lvl_cls}"))
        line.compose_add_child(Static(msg,   classes="srv-msg", markup=True))
        scroll.mount(line)
        scroll.scroll_end(animate=False)

    def set_running(self, running: bool) -> None:
        self.running = running
        self.query_one("#btn-srv-start").display   = not running
        self.query_one("#btn-srv-stop").display    = running
        self.query_one("#btn-srv-restart").display = running

        title = self.query_one("#srv-title", Static)
        if running:
            title.update(Text.from_markup("[#3a3a3a]SERVER OUTPUT[/]  [bold #44B78B]:8000 RUNNING[/]"))
        else:
            title.update("SERVER OUTPUT")

    # ── Messages ──────────────────────────────────────────────
    class StartServer(Message):   pass
    class StopServer(Message):    pass
    class RestartServer(Message): pass


# ── Command output panel ─────────────────────────────────────────────────────

class CommandPanel(Vertical):
    DEFAULT_CSS = """
    CommandPanel {
        height: 1fr;
    }
    #cmd-header {
        height: 3;
        background: #0f0f0f;
        border-bottom: tall #1a1a1a;
        padding: 0 2;
        align: left middle;
    }
    #cmd-title { color: #3a3a3a; text-style: bold; width: 1fr; }
    #cmd-scroll { height: 1fr; background: #0a0a0a; padding: 0 1; }
    .cmd-line   { color: #555555; padding: 0 1; }
    .cmd-prompt { color: #1e6e42; }
    .cmd-dim    { color: #1e1e1e; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="cmd-header"):
            yield Static("COMMAND OUTPUT", id="cmd-title")
            yield Button("✕ Clear", id="btn-clear", classes="btn-action")
        with ScrollableContainer(id="cmd-scroll"):
            yield Static(
                "[#1e1e1e]── Django Manager ready ─────────────────────────────[/]\n"
                "[#1e6e42]›[/] Type [bold #44B78B]django <command>[/] or [bold #56b6c2]manager <command>[/]",
                id="cmd-welcome",
                markup=True,
                classes="cmd-line",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-clear":
            scroll = self.query_one("#cmd-scroll", ScrollableContainer)
            scroll.remove_children()
            scroll.mount(Static(
                "[#1e1e1e]── Output cleared ──────────────────────────────────[/]",
                markup=True, classes="cmd-line",
            ))

    def append(self, text: str, markup: bool = True) -> None:
        scroll = self.query_one("#cmd-scroll", ScrollableContainer)
        scroll.mount(Static(text, markup=markup, classes="cmd-line"))
        scroll.scroll_end(animate=False)

    def append_badges(self, *badges: tuple[str, str]) -> None:
        """badges = list of (label, kind) tuples."""
        row = "  ".join(_badge(label, kind) for label, kind in badges)
        self.append(row)


# ── Input bar ────────────────────────────────────────────────────────────────

class InputBar(Horizontal):
    DEFAULT_CSS = """
    InputBar {
        height: 3;
        background: #0f0f0f;
        border-top: tall #1a1a1a;
        align: left middle;
        dock: bottom;
    }
    #ib-prefix {
        width: 4; height: 3;
        color: #1e6e42; content-align: center middle;
        background: #111111;
        border-right: tall #1a1a1a;
    }
    #ib-input {
        width: 1fr;
        background: transparent;
        border: none;
        color: #44B78B;
        height: 3;
        padding: 0 2;
    }
    #ib-input:focus { border: none; }
    #ib-send {
        background: #092E20; color: #44B78B;
        border: tall #1a3d28; height: 3;
        min-width: 10; content-align: center middle;
    }
    #ib-send:hover { background: #0d3d28; border: tall #44B78B; }
    """

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def compose(self) -> ComposeResult:
        yield Static("›", id="ib-prefix")
        yield Input(
            placeholder="django migrate  /  manager docs  /  django runserver",
            id="ib-input",
        )
        yield Button("RUN ▶", id="ib-send")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ib-send":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        inp = self.query_one("#ib-input", Input)
        val = inp.value.strip()
        if val:
            inp.value = ""
            self.post_message(self.Submitted(val))


# ── Dashboard screen ─────────────────────────────────────────────────────────

class DashboardScreen(Screen):
    """Main project control centre."""

    BINDINGS = [
        Binding("ctrl+r", "start_server",  "Runserver", show=False),
        Binding("ctrl+s", "stop_server",   "Stop",      show=False),
        Binding("escape", "go_home",        "Home",      show=False),
    ]

    CSS = """
    DashboardScreen { background: #0a0a0a; layout: vertical; }

    #dash-header {
        height: 3;
        background: #0f0f0f;
        border-bottom: tall #1a1a1a;
        padding: 0 2;
        align: left middle;
    }
    #dh-project { color: #44B78B; text-style: bold; }
    #dh-sep     { color: #1e1e1e; width: 3; content-align: center middle; }
    #dh-path    { color: #3a3a3a; width: 1fr; }
    .dh-badge   { height: 3; padding: 0 1; content-align: center middle; margin: 0 1; }
    .dh-badge-blue   { background: #0d1f2d; color: #61afef; border: tall #1a3a50; }
    .dh-badge-green  { background: #0a1f14; color: #44B78B; border: tall #092E20; }
    .dh-badge-cyan   { background: #0d1f20; color: #56b6c2; border: tall #1a3a3d; }
    #server-running-badge {
        background: #0a1f14; color: #44B78B; border: tall #092E20;
        height: 3; padding: 0 2; content-align: center middle; margin-right: 1;
    }
    #server-running-badge.hidden { display: none; }

    #dash-body  { height: 1fr; layout: horizontal; overflow: hidden; }
    #dash-main  { width: 1fr; layout: vertical;  overflow: hidden; }
    """

    def __init__(self, cfg: Optional[ProjectConfig] = None) -> None:
        super().__init__()
        self.cfg          = cfg
        self._server_proc: Optional[asyncio.subprocess.Process] = None
        self._server_task: Optional[asyncio.Task]               = None

    def compose(self) -> ComposeResult:
        project_name = self.cfg.name if self.cfg else "my_project"
        project_path = str(self.cfg.path) if self.cfg else "~/projects/my_project"
        py_ver       = self.cfg.python_ver if self.cfg else "3.12"
        dj_ver       = self.cfg.django_ver if self.cfg else "5.0"

        # Header
        with Horizontal(id="dash-header"):
            yield Static(project_name, id="dh-project")
            yield Static("|",          id="dh-sep")
            yield Static(project_path, id="dh-path")
            yield Static(f"Django {dj_ver}", classes="dh-badge dh-badge-blue")
            yield Static(f"Python {py_ver}", classes="dh-badge dh-badge-green")
            yield Static("● RUNNING :8000", id="server-running-badge")
            yield Button("⌂ Home", id="btn-go-home", classes="btn-action")

        # Body
        with Horizontal(id="dash-body"):
            yield Sidebar()
            with Vertical(id="dash-main"):
                yield ServerPanel()
                yield CommandPanel()
                yield InputBar()

    def on_mount(self) -> None:
        # Hide server running badge initially
        self.query_one("#server-running-badge").add_class("hidden")

    # ── Server control ────────────────────────────────────────

    def on_server_panel_start_server(self) -> None:
        self.run_worker(self._start_server(), exclusive=False)

    def on_server_panel_stop_server(self) -> None:
        self._stop_server()

    def on_server_panel_restart_server(self) -> None:
        self._stop_server()
        self.run_worker(self._start_server(), exclusive=False)

    async def _start_server(self) -> None:
        if not self.cfg:
            self.query_one(CommandPanel).append("[#e06c75]No project loaded.[/]", markup=True)
            return

        srv_panel = self.query_one(ServerPanel)
        srv_panel.set_running(True)
        self.query_one("#server-running-badge").remove_class("hidden")

        self.query_one(CommandPanel).append_badges(
            ("RUNSERVER", "ok"),
            ("localhost:8000", "info"),
            (f"Django {self.cfg.django_ver}", "neutral"),
        )

        try:
            self._server_proc = await start_runserver(self.cfg.path)
        except Exception as e:
            srv_panel.append_line(_ts(), "ERROR", str(e))
            srv_panel.set_running(False)
            return

        async for line in self._server_proc.stdout:
            text = line.decode("utf-8", errors="replace").rstrip()
            if not text:
                continue
            # Classify line
            if "Starting development server" in text:
                srv_panel.append_line(_ts(), "OK", f"[bold #44B78B]{text}[/]")
            elif "Watching for file changes" in text or "Django version" in text:
                srv_panel.append_line(_ts(), "OK", text)
            elif " 200 " in text:
                srv_panel.append_line(_ts(), "OK", _colorise_request(text))
            elif " 404 " in text or " 500 " in text:
                srv_panel.append_line(_ts(), "WARN", _colorise_request(text))
            elif "Error" in text or "Exception" in text:
                srv_panel.append_line(_ts(), "ERROR", f"[#e06c75]{text}[/]")
            else:
                srv_panel.append_line(_ts(), "INFO", text)

        await self._server_proc.wait()
        srv_panel.set_running(False)
        self.query_one("#server-running-badge").add_class("hidden")
        srv_panel.append_line(_ts(), "INFO", "Server stopped.")

    def _stop_server(self) -> None:
        if self._server_proc:
            self._server_proc.terminate()
            self._server_proc = None
        self.query_one(ServerPanel).set_running(False)
        self.query_one("#server-running-badge").add_class("hidden")

    # ── Command input ─────────────────────────────────────────

    def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        raw = event.value.strip()
        self.run_worker(self._handle_command(raw), exclusive=False)

    async def _handle_command(self, raw: str) -> None:
        panel = self.query_one(CommandPanel)
        panel.append(
            f"[#1e6e42]$[/] [bold #888888]{raw}[/]",
        )

        parts = raw.lower().split()
        if not parts:
            return

        # ── django <command> ──────────────────────────────────
        if parts[0] == "django":
            cmd  = parts[1] if len(parts) > 1 else ""
            args = parts[2:] if len(parts) > 2 else []

            if cmd == "runserver":
                panel.append_badges(("RUNSERVER", "info"))
                self.on_server_panel_start_server()
                return

            if not self.cfg:
                panel.append("[#e06c75]No project loaded.[/]", markup=True)
                return

            panel.append(f"[#3a3a3a]Running: python manage.py {cmd}...[/]", markup=True)
            output_lines = []
            try:
                async for line in run_django_command(
                    self.cfg.path, cmd, args, self.cfg.python_ver
                ):
                    panel.append(f"  [#555555]{line}[/]", markup=True)
                    output_lines.append(line)

                # Post-run badges
                if any("error" in l.lower() for l in output_lines):
                    panel.append_badges(("ERROR", "err"), (cmd.upper(), "neutral"))
                elif output_lines:
                    panel.append_badges(("OK", "ok"), (cmd.upper(), "neutral"))
                else:
                    panel.append_badges(("OK", "ok"), ("NO OUTPUT", "neutral"))

            except FileNotFoundError:
                panel.append_badges(("ERROR", "err"), ("manage.py not found", "neutral"))

        # ── manager <command> ─────────────────────────────────
        elif parts[0] == "manager":
            cmd = parts[1] if len(parts) > 1 else ""
            await self._handle_manager_cmd(cmd, panel)

        else:
            panel.append(
                f"[#e06c75]Unknown prefix.[/] Use [bold #44B78B]django[/] or [bold #56b6c2]manager[/]",
                markup=True,
            )
            panel.append_badges(("ERROR", "err"), ("unknown command", "neutral"))

    async def _handle_manager_cmd(self, cmd: str, panel: CommandPanel) -> None:
        match cmd:
            case "docs":
                panel.append("[bold #56b6c2]── DJANGO MANAGER COMMANDS ────────────────────[/]", markup=True)
                cmds = [
                    ("manager create",   "Create a new Django project"),
                    ("manager open",     "Open an existing project"),
                    ("manager docs",     "Show this reference"),
                    ("manager add",      "Add a package via uv"),
                    ("manager update",   "Update all packages"),
                    ("manager lock",     "Regenerate uv.lock"),
                    ("manager env",      "Show virtual environment info"),
                ]
                for c, desc in cmds:
                    panel.append(
                        f"  [bold #56b6c2]{c:<22}[/] [#3a3a3a]{desc}[/]",
                        markup=True,
                    )
                panel.append("[#1e1e1e]──────────────────────────────────────────────────[/]", markup=True)
                panel.append_badges(("MANAGER DOCS", "info"))

            case "env":
                if self.cfg:
                    panel.append(
                        f"  [#3a3a3a]Project:[/]  [#44B78B]{self.cfg.name}[/]\n"
                        f"  [#3a3a3a]venv:[/]     [#44B78B]{self.cfg.venv_path}[/]\n"
                        f"  [#3a3a3a]Python:[/]   [#44B78B]{self.cfg.python_ver}[/]\n"
                        f"  [#3a3a3a]Django:[/]   [#44B78B]{self.cfg.django_ver}[/]",
                        markup=True,
                    )
                panel.append_badges(("ENV INFO", "info"))

            case "add":
                panel.append("[#3a3a3a]Usage: manager add <package>[/]", markup=True)
                panel.append("[#3a3a3a]Example: manager add djangorestframework[/]", markup=True)
                panel.append_badges(("HINT", "warn"))

            case "lock":
                panel.append("[#3a3a3a]Regenerating uv.lock...[/]", markup=True)
                panel.append_badges(("DONE", "ok"), ("uv.lock", "neutral"))

            case _:
                panel.append(f"[#e06c75]Unknown manager command: {cmd}[/]", markup=True)
                panel.append_badges(("ERROR", "err"))

    # ── Misc ──────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-go-home":
            self.action_go_home()

    def action_go_home(self) -> None:
        self._stop_server()
        from .home import HomeScreen
        self.app.switch_screen(HomeScreen())

    def action_start_server(self) -> None:
        self.run_worker(self._start_server(), exclusive=False)

    def action_stop_server(self) -> None:
        self._stop_server()


# ── Request line coloriser ────────────────────────────────────────────────────

def _colorise_request(line: str) -> str:
    """Add Rich markup to Django dev server request lines."""
    line = re.sub(r'"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)',
                  r'"[bold #44B78B]\1[/]', line)
    line = re.sub(r' 200 ', r' [bold #44B78B]200[/] ', line)
    line = re.sub(r' (404|403|401) ', r' [bold #e06c75]\1[/] ', line)
    line = re.sub(r' (500|502|503) ', r' [bold #e06c75]\1[/] ', line)
    return line
