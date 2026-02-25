"""
Django Manager — Install Screen
Runs project creation steps and streams output.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar, Static

from ..core.config import APP_VERSION
from ..core.operations import ProjectConfig, create_project, StepResult

STEP_IDS = ["mkdir", "venv", "activate", "install", "startproject", "lockfile"]
STEP_LABELS = {
    "mkdir":       ("📁", "Creating project directory"),
    "venv":        ("🐍", "Setting up Python environment"),
    "activate":    ("⚡", "Activating virtual environment"),
    "install":     ("📦", "Installing packages via uv"),
    "startproject":("🔨", "Running django-admin startproject"),
    "lockfile":    ("📄", "Generating pyproject.toml + uv.lock"),
}


class StepRow(Horizontal):
    """One install step row: icon | label | status."""

    DEFAULT_CSS = """
    StepRow {
        height: 3;
        padding: 0 2;
        border-bottom: tall #1a1a1a;
        align: left middle;
    }
    .sr-icon   { width: 4; content-align: center middle; }
    .sr-label  { width: 1fr; color: #555555; }
    .sr-status { width: 14; content-align: right middle; }
    .sr-wait   { color: #1e1e1e; }
    .sr-run    { color: #e5c07b; }
    .sr-done   { color: #44B78B; }
    .sr-err    { color: #e06c75; }
    """

    def __init__(self, step_id: str) -> None:
        super().__init__()
        self.step_id = step_id
        icon, label  = STEP_LABELS[step_id]
        self._icon   = icon
        self._label  = label

    def compose(self) -> ComposeResult:
        yield Static(self._icon,  classes="sr-icon")
        yield Static(self._label, classes="sr-label", id=f"sl-{self.step_id}")
        yield Static("○ WAITING", classes="sr-status sr-wait", id=f"ss-{self.step_id}")

    def set_running(self) -> None:
        self.query_one(f"#ss-{self.step_id}", Static).update("● RUNNING")
        self.query_one(f"#ss-{self.step_id}", Static).set_classes("sr-status sr-run")

    def set_done(self, msg: str = "") -> None:
        self.query_one(f"#ss-{self.step_id}", Static).update("✓ DONE")
        self.query_one(f"#ss-{self.step_id}", Static).set_classes("sr-status sr-done")
        if msg:
            self.query_one(f"#sl-{self.step_id}", Static).update(msg)

    def set_error(self, msg: str = "") -> None:
        self.query_one(f"#ss-{self.step_id}", Static).update("✗ FAILED")
        self.query_one(f"#ss-{self.step_id}", Static).set_classes("sr-status sr-err")
        if msg:
            self.query_one(f"#sl-{self.step_id}", Static).update(msg)


class InstallScreen(Screen):
    """Runs all creation steps and shows live progress."""

    CSS = """
    InstallScreen {
        align: center middle;
        background: #0a0a0a;
    }

    #install-wrap {
        width: 70;
        height: auto;
        background: #111111;
        border: tall #1a1a1a;
        padding: 0;
    }

    #inst-header {
        height: 3;
        background: #0f0f0f;
        border-bottom: tall #1a1a1a;
        padding: 0 2;
        align: left middle;
    }

    #inst-title {
        color: #44B78B;
        text-style: bold;
    }

    #inst-sub {
        color: #3a3a3a;
        padding: 1 2;
        height: 3;
    }

    #steps-container {
        height: auto;
        border-bottom: tall #1a1a1a;
    }

    #inst-progress {
        margin: 1 2;
        height: 1;
    }

    #log-container {
        height: 14;
        background: #0a0a0a;
        border: tall #1a1a1a;
        margin: 0 2 2 2;
        overflow-y: auto;
        padding: 1 1;
    }

    .log-entry { color: #7a7a7a; }
    .log-prompt { color: #1e6e42; }
    .log-ok     { color: #44B78B; }
    .log-err    { color: #e06c75; }
    .log-info   { color: #61afef; }
    """

    def __init__(self, cfg: ProjectConfig) -> None:
        super().__init__()
        self.cfg      = cfg
        self._failed  = False

    def compose(self) -> ComposeResult:
        with Container(id="install-wrap"):
            yield Static(
                f"[bold #44B78B]Creating Project[/]  [#1e1e1e]v{APP_VERSION}[/]",
                id="inst-header", markup=True,
            )
            yield Static(
                f"Setting up [bold #44B78B]{self.cfg.name}[/]  "
                f"[#3a3a3a]Python {self.cfg.python_ver} + Django {self.cfg.django_ver}[/]",
                id="inst-sub", markup=True,
            )

            with Vertical(id="steps-container"):
                for sid in STEP_IDS:
                    yield StepRow(step_id=sid)

            yield ProgressBar(id="inst-progress", total=len(STEP_IDS), show_eta=False)

            with ScrollableContainer(id="log-container"):
                yield Static(
                f"[#1e6e42]$[/] Starting project creation...",
                markup=True,
                classes="log-entry",
                id="log-area",
            )

    def on_mount(self) -> None:
        self.run_worker(self._run_install(), exclusive=True)

    # ── Worker ────────────────────────────────────────────────

    async def _run_install(self) -> None:
        progress   = 0
        step_index = 0
        prog_bar   = self.query_one(ProgressBar)

        # Mark first step running
        self._get_row("mkdir").set_running()

        async for step_id, result in create_project(self.cfg):
            row = self._get_row(step_id)
            if result.ok:
                row.set_done(result.message)
                self._log(f"[#44B78B]✓[/] {result.message}", markup=True)
                if result.detail:
                    self._log(f"  {result.detail}", markup=False)
            else:
                row.set_error(result.message)
                self._log(f"[#e06c75]✗ {result.message}[/]", markup=True)
                if result.detail:
                    self._log(f"  {result.detail}", markup=False)
                self._failed = True
                break

            progress   += 1
            step_index += 1
            prog_bar.advance(1)

            # Prime next step as running
            if step_index < len(STEP_IDS) and not self._failed:
                next_id = STEP_IDS[step_index]
                self._get_row(next_id).set_running()
                self._log(f"[#1e6e42]$[/] {STEP_LABELS[next_id][1]}...", markup=True)

        if not self._failed:
            self._log("[#44B78B]✓ All done! Launching dashboard...[/]", markup=True)
            import asyncio
            await asyncio.sleep(1.2)
            from .success import SuccessScreen
            self.app.switch_screen(SuccessScreen(cfg=self.cfg))
        else:
            self._log("[#e06c75]✗ Setup failed. Press Esc to go back.[/]", markup=True)

    # ── Helpers ───────────────────────────────────────────────

    def _get_row(self, step_id: str) -> StepRow:
        for row in self.query(StepRow):
            if row.step_id == step_id:
                return row
        raise KeyError(step_id)

    def _log(self, text: str, markup: bool = False) -> None:
        log = self.query_one("#log-area", Static)
        if isinstance(getattr(log, "renderable", None), Text):
            existing = log.renderable
        else:
            existing = Text(str(getattr(log, "renderable", "") or ""))
        new_line = Text.from_markup(text) if markup else Text(text)
        if existing.plain:
            existing.append("\n")
        existing.append_text(new_line)
        log.update(existing)
        # Scroll to bottom
        container = self.query_one("#log-container", ScrollableContainer)
        container.scroll_end(animate=False)

    # ── Escape goes back to wizard ────────────────────────────
    BINDINGS = [Binding("escape", "go_back", "Back")]

    def action_go_back(self) -> None:
        from .wizard import WizardScreen
        self.app.switch_screen(WizardScreen())
