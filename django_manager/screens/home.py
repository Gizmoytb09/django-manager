"""
Django Manager — Home Screen
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static

from ..core.config import APP_VERSION

LOGO = """\
[bold #44B78B]██████╗      ███╗   ███╗
██╔══██╗     ████╗ ████║
██║  ██║     ██╔████╔██║
██║  ██║     ██║╚██╔╝██║
██████╔╝     ██║ ╚═╝ ██║
╚═════╝      ╚═╝     ╚═╝[/]"""

SUBTITLE = "[bold #1e6e42]D J A N G O   M A N A G E R[/]"
DIVIDER  = "[#1a3d28]" + "━" * 52 + "[/]"


class HomeScreen(Screen):
    """Main landing screen."""

    CSS = """
    HomeScreen {
        align: center middle;
        background: #0a0a0a;
    }

    #home-wrap {
        width: 54;
        height: auto;
        align: center middle;
    }

    #logo {
        content-align: center middle;
        width: 100%;
        height: 8;
    }

    #subtitle {
        content-align: center middle;
        width: 100%;
        height: 1;
    }

    #divider {
        content-align: center middle;
        width: 100%;
        height: 1;
        margin-bottom: 2;
    }

    #btn-create {
        width: 100%;
        height: 5;
        background: #092E20;
        color: #44B78B;
        border: tall #44B78B;
        text-style: bold;
        content-align: center middle;
        margin-bottom: 1;
    }

    #btn-create:hover {
        background: #0d3d28;
        border: tall #6ddba8;
        color: #6ddba8;
    }

    #btn-create:focus {
        background: #0f4530;
        border: tall #6ddba8;
    }

    .home-secondary {
        width: 100%;
        height: 3;
        background: #111111;
        color: #3a3a3a;
        border: tall #1a1a1a;
        content-align: left middle;
        padding-left: 2;
        margin-bottom: 1;
    }

    .home-secondary:hover {
        background: #151515;
        color: #888888;
        border: tall #2a2a2a;
    }

    .home-secondary:focus {
        background: #151515;
        color: #888888;
        border: tall #2a2a2a;
    }

    #status-row {
        width: 100%;
        height: 1;
        margin-top: 2;
        padding-top: 1;
        border-top: tall #1e1e1e;
        align: left middle;
    }

    #status-left {
        color: #1e1e1e;
        width: 1fr;
    }

    #keybinds-row {
        width: 100%;
        content-align: center middle;
        color: #1e1e1e;
        height: 1;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("c", "create",   "Create Project", show=False),
        Binding("o", "open",     "Open Project",   show=False),
        Binding("d", "docs",     "Docs",           show=False),
        Binding("s", "settings", "Settings",       show=False),
        Binding("q", "app.quit", "Quit",           show=False),
    ]

    def on_mount(self) -> None:
        self._apply_responsive()

    def on_resize(self, event) -> None:  # type: ignore[override]
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        wrap = self.query_one("#home-wrap")
        width = max(40, min(self.size.width - 4, 60))
        wrap.styles.width = width
        compact = self.size.height < 28
        self.query_one("#logo").styles.height = 6 if compact else 8
        self.query_one("#btn-create").styles.height = 4 if compact else 5
        for btn in self.query(".home-secondary"):
            btn.styles.height = 2 if compact else 3

    def compose(self) -> ComposeResult:
        with Container(id="home-wrap"):
            yield Static(LOGO,     id="logo",    markup=True)
            yield Static(SUBTITLE, id="subtitle", markup=True)
            yield Static(DIVIDER,  id="divider",  markup=True)

            yield Button("  ✦   CREATE DJANGO PROJECT", id="btn-create")
            yield Button("  ▶   OPEN EXISTING PROJECT", id="btn-open",     classes="home-secondary")
            yield Button("  ◉   DOCUMENTATION",         id="btn-docs",     classes="home-secondary")
            yield Button("  ⚙   SETTINGS",              id="btn-settings", classes="home-secondary")

            yield Static(
                f"[#1e1e1e]● [/][#1e1e1e]django-manager v{APP_VERSION}  ·  textual + uv + rich[/]",
                id="status-left",
                markup=True,
            )
            yield Static(
                "[#1e1e1e]"
                "\\[c] Create  \\[o] Open  \\[d] Docs  \\[s] Settings  \\[q] Quit"
                "[/]",
                id="keybinds-row",
                markup=True,
            )

    # ── Button routing ────────────────────────────────────────
    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-create":   self.action_create()
            case "btn-open":     self.action_open()
            case "btn-docs":     self.notify("Documentation — coming soon", severity="information")
            case "btn-settings": self.notify("Settings — coming soon", severity="information")

    # ── Key actions ───────────────────────────────────────────
    def action_create(self) -> None:
        from .wizard import WizardScreen
        self.app.push_screen(WizardScreen())

    def action_open(self)     -> None:
        from .open_project import OpenProjectScreen
        self.app.push_screen(OpenProjectScreen())
    def action_docs(self)     -> None: self.notify("Documentation — coming soon")
    def action_settings(self) -> None: self.notify("Settings — coming soon")
