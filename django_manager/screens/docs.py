"""
Django Manager — Documentation Screen
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Static


QUICK_BADGE = "[bold #44B78B on #0a1f14] QUICK EXPLANATION [/]"

DOC_TABS: list[tuple[str, str]] = [
    ("overview", "Overview"),
    ("commands", "Commands"),
    ("workflow", "Workflow"),
    ("uses", "Uses"),
    ("troubleshooting", "Troubleshooting"),
]

DOC_CONTENT: dict[str, str] = {
    "overview": f"""
{QUICK_BADGE}
[#3a3a3a]Django Manager wraps common Django tasks into a fast TUI so you can
create projects, run server commands, and manage environments without leaving
the terminal.[/]

[#56b6c2]What You Get[/]
• One place to run [bold]django <command>[/] and [bold]manager <command>[/].
• A guided wizard for new projects (Python, Django, starter packs).
• A project dashboard with server output + command output.

[#56b6c2]Navigation[/]
• Use the sidebar to trigger quick actions.
• Use the bottom input bar for precise commands.
• Switch views when in Tabs layout.
""",
    "commands": """
[#56b6c2]Django Commands[/]
• [bold]django runserver[/] — start the dev server.
• [bold]django migrate[/] — apply migrations.
• [bold]django makemigrations[/] — create new migrations.
• [bold]django showmigrations[/] — list migrations.
• [bold]django shell[/] — start the Django shell (manual in terminal).

[#56b6c2]Manager Commands[/]
• [bold]manager docs[/] — show the built-in docs.
• [bold]manager add <pkg>[/] — add a package via uv.
• [bold]manager packages[/] — list installed packages.
• [bold]manager remove <pkg>[/] — remove packages.
• [bold]manager remove --tui[/] — interactive removal.
• [bold]manager lock[/] — regenerate uv.lock.
• [bold]manager env[/] — show the active env summary.

[#56b6c2]Tip[/]
• The command bar supports history in your terminal and auto-scrolling output.
""",
    "workflow": """
[#56b6c2]New Project (Recommended)[/]
• Go to Home → Create Django Project.
• Pick Python + Django versions.
• Choose optional starter packs.
• The wizard creates the env, installs packages, and runs startproject.

[#56b6c2]Open Existing Project[/]
• Select the project’s [bold]manage.py[/].
• Select the correct virtual environment folder.
• Django Manager validates that Django is installed in that venv.

[#56b6c2]Server Workflow[/]
• Click [bold]Runserver[/] or type [bold]django runserver[/].
• Logs stream into Server Output; commands appear in Command Output.
""",
    "uses": """
[#56b6c2]Uses[/]
• Quick demos and learning sessions.
• Running migrations without context switching.
• Lightweight ops tasks (lockfile regen, env checks).
• Onboarding new developers with a consistent UI.

[#56b6c2]Best Practices[/]
• Keep the project root clean (manage.py at the root you open).
• Prefer a per-project virtual environment.
• Use [bold]uv[/] to manage dependencies and lockfiles.
""",
    "troubleshooting": """
[#56b6c2]Common Issues[/]
• [bold]manage.py not found[/] — make sure you selected manage.py itself.
• [bold]Django missing[/] — install Django inside the selected venv.
• [bold]No venv detected[/] — select the venv folder (has pyvenv.cfg).

[#56b6c2]Install Django (inside venv)[/]
• Activate the venv, then run [bold]uv pip install django[/].

[#56b6c2]Runserver Problems[/]
• Port in use: try [bold]django runserver 8001[/].
• No output: check the Command Output for errors.
""",
}


class DocsScreen(Screen):
    CSS = """
    DocsScreen {
        align: center middle;
        background: #0a0a0a;
    }

    #docs-wrap {
        width: 70;
        height: auto;
        background: #111111;
        border: tall #1a1a1a;
        padding: 2 3;
    }

    #docs-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #docs-tabs { height: 3; align: center middle; margin-bottom: 1; }
    .docs-tab {
        height: 3;
        padding: 0 2;
        margin: 0 1;
        background: #111111;
        color: #555555;
        border: tall #1a1a1a;
        content-align: center middle;
        min-width: 14;
    }
    .docs-tab--active {
        background: #0a1f14;
        color: #44B78B;
        border: tall #092E20;
        text-style: bold;
    }

    #docs-scroll {
        height: 16;
        background: #0a0a0a;
        border: tall #1a1a1a;
        padding: 1 2;
    }

    #docs-actions { height: 3; margin-top: 2; align: center middle; }
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

    active_tab: reactive[str] = reactive("overview")

    def compose(self) -> ComposeResult:
        with Container(id="docs-wrap"):
            yield Static("Documentation", id="docs-title")
            with Horizontal(id="docs-tabs"):
                for tab_id, label in DOC_TABS:
                    classes = "docs-tab" + (" docs-tab--active" if tab_id == self.active_tab else "")
                    yield Button(label, id=f"tab-{tab_id}", classes=classes)
            with ScrollableContainer(id="docs-scroll"):
                yield Static("", id="docs-body")
            with Horizontal(id="docs-actions"):
                yield Button("Close", id="btn-close")

    def on_mount(self) -> None:
        self._apply_responsive()
        self._render_tab()

    def on_resize(self, event) -> None:  # type: ignore[override]
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        wrap = self.query_one("#docs-wrap")
        width = max(56, min(self.size.width - 6, 96))
        wrap.styles.width = width
        scroll = self.query_one("#docs-scroll")
        scroll.styles.height = max(10, min(self.size.height - 10, 24))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.app.pop_screen()
            return
        if event.button.id and event.button.id.startswith("tab-"):
            self.active_tab = event.button.id.replace("tab-", "")
            self._sync_tabs()
            self._render_tab()

    def _sync_tabs(self) -> None:
        for tab_id, _ in DOC_TABS:
            btn = self.query_one(f"#tab-{tab_id}", Button)
            if tab_id == self.active_tab:
                btn.add_class("docs-tab--active")
            else:
                btn.remove_class("docs-tab--active")

    def _render_tab(self) -> None:
        body = self.query_one("#docs-body", Static)
        content = DOC_CONTENT.get(self.active_tab, "")
        body.update(Text.from_markup(content))
