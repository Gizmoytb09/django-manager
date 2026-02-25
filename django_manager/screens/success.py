"""
Django Manager — Success Screen
"""
from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar, Static

from ..core.operations import ProjectConfig


class SuccessScreen(Screen):
    CSS = """
    SuccessScreen {
        align: center middle;
        background: #0a0a0a;
    }

    #success-wrap {
        width: 62;
        height: auto;
        background: #111111;
        border: tall #1e6e42;
        padding: 2 3;
        align: center middle;
    }

    #s-icon  { content-align: center middle; width: 100%; height: 3; }
    #s-title {
        content-align: center middle; width: 100%;
        color: #44B78B; text-style: bold; height: 2;
    }
    #s-sub   {
        content-align: center middle; width: 100%;
        color: #555555; height: 2; margin-bottom: 1;
    }

    #badges-row {
        height: 3; width: 100%;
        align: center middle;
        margin-bottom: 1;
    }

    .badge {
        height: 3;
        padding: 0 2;
        margin: 0 1;
        content-align: center middle;
    }

    .badge-green  { background: #0a1f14; color: #44B78B; border: tall #092E20; }
    .badge-blue   { background: #0d1f2d; color: #61afef; border: tall #1a3a50; }
    .badge-cyan   { background: #0d1f20; color: #56b6c2; border: tall #1a3a3d; }
    .badge-yellow { background: #1f1a0d; color: #e5c07b; border: tall #3a2e1a; }

    #s-detail {
        background: #0a0a0a; border: tall #1a1a1a;
        padding: 1 2; height: auto; margin-bottom: 2; width: 100%;
    }

    .detail-row {
        height: 2;
        align: left middle;
    }
    .detail-label { color: #3a3a3a; width: 16; }
    .detail-value { color: #44B78B; width: 1fr; }

    #s-redirect { color: #1e1e1e; content-align: center middle; width: 100%; height: 1; }
    #s-progress { margin: 1 0; width: 100%; }

    #s-dash-btn {
        width: 100%;
        height: 3;
        background: #092E20;
        color: #44B78B;
        border: tall #44B78B;
        text-style: bold;
        content-align: center middle;
        margin-top: 1;
    }
    #s-dash-btn:hover { background: #0d3d28; color: #6ddba8; border: tall #6ddba8; }
    """

    def __init__(self, cfg: ProjectConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        with Container(id="success-wrap"):
            yield Static("✦", id="s-icon")
            yield Static("PROJECT CREATED", id="s-title")
            yield Static(
                f"{self.cfg.name} is ready.  venv active.  packages installed.",
                id="s-sub",
            )

            # Badges
            with Horizontal(id="badges-row"):
                yield Static(f"✓ Python {self.cfg.python_ver}", classes="badge badge-green")
                yield Static(f"✓ Django {self.cfg.django_ver}", classes="badge badge-blue")
                yield Static("✓ venv active",      classes="badge badge-yellow")
                yield Static("✓ uv.lock",          classes="badge badge-cyan")

            # Detail table
            with Vertical(id="s-detail"):
                for label, value in [
                    ("Location",    str(self.cfg.path)),
                    ("Environment", ".venv (active)"),
                    ("Packages",    ", ".join(self.cfg.packages)),
                    ("Lockfile",    "uv.lock ✓"),
                ]:
                    with Horizontal(classes="detail-row"):
                        yield Static(label, classes="detail-label")
                        yield Static(value, classes="detail-value")

            yield Static("Redirecting to project dashboard...", id="s-redirect")
            yield ProgressBar(id="s-progress", total=100, show_eta=False)
            yield Button("▶  Open Dashboard Now", id="s-dash-btn")

    def on_mount(self) -> None:
        self._apply_responsive()
        self.run_worker(self._countdown())

    def on_resize(self, event) -> None:  # type: ignore[override]
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        wrap = self.query_one("#success-wrap")
        width = max(44, min(self.size.width - 4, 72))
        wrap.styles.width = width

    async def _countdown(self) -> None:
        bar = self.query_one(ProgressBar)
        for i in range(100):
            await asyncio.sleep(0.03)
            bar.advance(1)
        self._go_dashboard()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "s-dash-btn":
            self._go_dashboard()

    def _go_dashboard(self) -> None:
        from .dashboard import DashboardScreen
        self.app.switch_screen(DashboardScreen(cfg=self.cfg))
