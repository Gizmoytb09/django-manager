"""
Django Manager — Create Project Wizard
Steps: 1 Name → 2 Python → 3 Django → 4 Options → 5 Auth & Migrations → Install
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from ..core.config import (
    APP_VERSION, DJANGO_VERSIONS, PYTHON_VERSIONS,
)
from ..core.operations import ProjectConfig


# ── Sidebar step list ──────────────────────────────────────────────────────

STEPS = [
    "Project Name",
    "Python Version",
    "Django Version",
    "Project Options",
    "Auth & Migrations",
]


class StepSidebar(Vertical):
    """Left column showing wizard progress."""

    current: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    StepSidebar {
        width: 24;
        background: #0f0f0f;
        border-right: tall #1a1a1a;
        padding: 2 1;
    }

    #steps-heading {
        color: #1e6e42;
        text-style: bold;
        margin-bottom: 1;
        padding-left: 1;
    }

    .step-row {
        height: 3;
        padding: 0 1;
        align: left middle;
        border: tall transparent;
        color: #1e1e1e;
    }

    .step-row--done    { color: #1e6e42; }
    .step-row--current { color: #44B78B; background: #0a1f14; border: tall #092E20; }
    .step-row--pending { color: #1e1e1e; }

    #sidebar-footer {
        margin-top: 3;
        padding: 1;
        border-top: tall #1a1a1a;
        color: #1e1e1e;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("PROJECT SETUP", id="steps-heading")
        for i, name in enumerate(STEPS):
            num = f" {i+1} "
            yield Static(f"{num} {name}", id=f"step-row-{i}", classes="step-row step-row--pending")
        yield Static(
            "[#1e1e1e]Powered by\nuv · Rich · Textual[/]",
            id="sidebar-footer",
            markup=True,
        )

    def watch_current(self, val: int) -> None:
        for i in range(len(STEPS)):
            el = self.query_one(f"#step-row-{i}", Static)
            if i < val:
                el.set_classes("step-row step-row--done")
            elif i == val:
                el.set_classes("step-row step-row--current")
            else:
                el.set_classes("step-row step-row--pending")


# ── Individual step panes ──────────────────────────────────────────────────

class NameStep(Vertical):
    DEFAULT_CSS = """
    NameStep { padding: 2 3; height: auto; }
    #ns-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #ns-sub   { color: #555555; margin-bottom: 2; }
    .field-label { color: #555555; margin-bottom: 1; }
    #ns-preview {
        background: #111111; border: tall #1a1a1a;
        padding: 1 2; height: auto; margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Name Your Project", id="ns-title")
        yield Static("Choose a name and location for your Django project.", id="ns-sub")
        yield Static("PROJECT NAME", classes="field-label")
        yield Input(placeholder="my_django_project", id="project-name")
        yield Static("LOCATION", classes="field-label")
        yield Input(placeholder="~/projects/", id="project-location", value="~/projects/")
        yield Static("", id="ns-preview")

    def on_input_changed(self, event: Input.Changed) -> None:
        name = self.query_one("#project-name", Input).value or "my_project"
        loc  = self.query_one("#project-location", Input).value or "~/projects/"
        preview = (
            f"[#3a3a3a]Preview:[/]\n"
            f"[#555555]{loc}[/][bold #44B78B]{name}[/][#555555]/[/]\n"
            f"[#1e1e1e]  ├── manage.py\n"
            f"  ├── pyproject.toml\n"
            f"  ├── uv.lock\n"
            f"  └── {name}/[/]"
        )
        self.query_one("#ns-preview", Static).update(Text.from_markup(preview))


class PythonStep(Vertical):
    DEFAULT_CSS = """
    PythonStep { padding: 2 3; height: auto; }
    #py-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #py-sub   { color: #555555; margin-bottom: 2; }
    .field-label { color: #555555; margin-bottom: 1; }
    #py-grid  { height: auto; }
    .py-card  {
        height: 6; width: 1fr;
        background: #111111; border: tall #1a1a1a;
        align: center middle; content-align: center middle;
    }
    .py-card:hover     { border: tall #1e6e42; background: #0f1f17; }
    .py-card--selected { border: tall #44B78B; background: #0a1f14; }
    #py-cmd {
        background: #0a1f14; border: tall #092E20;
        padding: 1 2; height: auto; margin-top: 2;
    }
    """

    selected: reactive[str] = reactive("3.12")

    def compose(self) -> ComposeResult:
        yield Static("Python Version", id="py-title")
        yield Static("uv will install and manage the selected version automatically.", id="py-sub")
        yield Static("SELECT VERSION", classes="field-label")
        with Horizontal(id="py-grid"):
            for pv in PYTHON_VERSIONS:
                badge = f"\n[bold #1e6e42]{pv['badge']}[/]" if pv["badge"] else ""
                sel   = " py-card--selected" if pv["label"] == "3.12" else ""
                yield Static(
                    f"[bold #44B78B]{pv['label']}[/]{badge}",
                    id=f"py-{pv['label'].replace('.', '_')}",
                    classes=f"py-card{sel}",
                    markup=True,
                )
        yield Static(
            "[#1e6e42]UV WILL RUN[/]\n"
            "[#3a3a3a]$[/] [#888888]uv venv --python 3.12[/]\n"
            "[#3a3a3a]$[/] [#888888]source .venv/bin/activate[/]",
            id="py-cmd",
            markup=True,
        )

    def on_click(self, event) -> None:
        # Find which py-card was clicked
        widget = event.widget
        for pv in PYTHON_VERSIONS:
            card = self.query_one(f"#py-{pv['label'].replace('.', '_')}", Static)
            if widget is card:
                self.selected = pv["label"]
                break

    def watch_selected(self, val: str) -> None:
        for pv in PYTHON_VERSIONS:
            card = self.query_one(f"#py-{pv['label'].replace('.', '_')}", Static)
            if pv["label"] == val:
                card.add_class("py-card--selected")
            else:
                card.remove_class("py-card--selected")
        # Update command preview
        cmd = (
            f"[#1e6e42]UV WILL RUN[/]\n"
            f"[#3a3a3a]$[/] [#888888]uv venv --python {val}[/]\n"
            f"[#3a3a3a]$[/] [#888888]source .venv/bin/activate[/]"
        )
        self.query_one("#py-cmd", Static).update(Text.from_markup(cmd))


class DjangoStep(Vertical):
    DEFAULT_CSS = """
    DjangoStep { padding: 2 3; height: auto; }
    #dj-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #dj-sub   { color: #555555; margin-bottom: 2; }
    .field-label { color: #555555; margin-bottom: 1; }
    #dj-grid  { height: auto; }
    .dj-card  {
        height: 6; width: 1fr;
        background: #111111; border: tall #1a1a1a;
        align: center middle; content-align: center middle;
    }
    .dj-card:hover     { border: tall #1e6e42; background: #0f1f17; }
    .dj-card--selected { border: tall #44B78B; background: #0a1f14; }
    .dj-card--lts      { border: tall #092E20; }
    #dj-compat {
        background: #111111; border: tall #1a1a1a;
        padding: 1 2; height: auto; margin-top: 2;
    }
    """

    selected: reactive[str] = reactive("5.0")

    def compose(self) -> ComposeResult:
        yield Static("Django Version", id="dj-title")
        yield Static("Packages shown in starter packs will be filtered for compatibility.", id="dj-sub")
        yield Static("SELECT VERSION", classes="field-label")
        with Horizontal(id="dj-grid"):
            for dv in DJANGO_VERSIONS:
                lts_cls = " dj-card--lts" if dv["lts"] else ""
                sel_cls = " dj-card--selected" if dv["label"] == "5.0" else ""
                tag_col = "#1e6e42" if dv["lts"] else "#3a3a3a"
                yield Static(
                    f"[bold #888888]{dv['label']}[/]\n[{tag_col}]{dv['tag']}[/]",
                    id=f"dj-{dv['label'].replace('.', '_')}",
                    classes=f"dj-card{lts_cls}{sel_cls}",
                    markup=True,
                )
        yield Static("", id="dj-compat", markup=True)

    def on_mount(self) -> None:
        self._update_compat(self.selected)

    def on_click(self, event) -> None:
        widget = event.widget
        for dv in DJANGO_VERSIONS:
            card_id = f"dj-{dv['label'].replace('.', '_')}"
            card = self.query_one(f"#{card_id}", Static)
            if widget is card:
                self.selected = dv["label"]
                break

    def watch_selected(self, val: str) -> None:
        for dv in DJANGO_VERSIONS:
            card = self.query_one(f"#dj-{dv['label'].replace('.', '_')}", Static)
            if dv["label"] == val:
                card.add_class("dj-card--selected")
            else:
                card.remove_class("dj-card--selected")
        self._update_compat(val)

    def _update_compat(self, ver: str) -> None:
        compat = {
            "4.2": ["djangorestframework ≥3.14", "django-htmx ≥1.17", "django-allauth ≥0.58"],
            "5.0": ["djangorestframework ≥3.14", "django-htmx ≥1.17", "django-allauth ≥0.61"],
            "5.1": ["djangorestframework ≥3.15", "django-htmx ≥1.18", "django-allauth ≥0.63"],
            "5.2": ["djangorestframework ≥3.15", "django-htmx ≥1.19", "django-allauth ≥0.63"],
        }
        pkgs = compat.get(ver, [])
        tags = "  ".join(f"[#1e6e42]{p}[/]" for p in pkgs)
        text = f"[#3a3a3a]Compatible packages:[/]\n{tags}"
        self.query_one("#dj-compat", Static).update(Text.from_markup(text))


class OptionsStep(Vertical):
    DEFAULT_CSS = """
    OptionsStep { padding: 2 3; height: auto; }
    #op-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #op-sub   { color: #555555; margin-bottom: 2; }
    .opt-head { color: #555555; margin: 1 0 1 0; }

    .opt-row {
        height: auto;
        padding: 1 2;
        background: #111111;
        border: tall #1a1a1a;
        margin-bottom: 1;
    }
    .opt-row--selected {
        background: #0a1f14;
        border: tall #44B78B;
    }
    .opt-name { color: #888888; text-style: bold; }
    .opt-name--selected { color: #44B78B; }
    .opt-desc  { color: #3a3a3a; margin-top: 1; }

    #op-summary {
        background: #0f0f0f; border: tall #1a1a1a;
        padding: 1 2; height: auto; margin-top: 1;
    }
    """

    interactive: reactive[str] = reactive("htmx")
    css_framework: reactive[str] = reactive("bootstrap")
    auth_framework: reactive[str] = reactive("django")
    add_pytest: reactive[bool] = reactive(False)
    skip_auth_app: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static("Project Options", id="op-title")
        yield Static("Pick your stack preferences and extras.", id="op-sub")

        yield Static("Interactive", classes="opt-head")
        for key, label, desc in [
            ("htmx", "HTMX", "Install django-htmx and enable its middleware."),
            ("ajax", "Ajax", "Use standard Django views + fetch/XHR patterns."),
            ("jquery", "jQuery", "Include a jQuery-friendly layout baseline."),
        ]:
            sel = " opt-row--selected" if self.interactive == key else ""
            name_cls = "opt-name--selected" if self.interactive == key else "opt-name"
            yield Static(
                f"[{name_cls}]⚡ {label}[/{name_cls}]\n[opt-desc]{desc}[/opt-desc]",
                id=f"opt-interactive-{key}",
                classes=f"opt-row{sel}",
                markup=True,
            )

        yield Static("CSS Framework", classes="opt-head")
        for key, label, desc in [
            ("bootstrap", "Bootstrap", "Bootstrap-ready template layout."),
            ("tailwind", "Tailwind", "Tailwind-ready template layout."),
            ("none", "None (Django default)", "Keep Django's default homepage."),
        ]:
            sel = " opt-row--selected" if self.css_framework == key else ""
            name_cls = "opt-name--selected" if self.css_framework == key else "opt-name"
            yield Static(
                f"[{name_cls}]🎨 {label}[/{name_cls}]\n[opt-desc]{desc}[/opt-desc]",
                id=f"opt-css-{key}",
                classes=f"opt-row{sel}",
                markup=True,
            )

        yield Static("Authentication Framework", classes="opt-head")
        for key, label, desc in [
            ("django", "None (Django default)", "Use Django auth + generated templates."),
            ("allauth", "django-allauth", "Install allauth and generate overrides."),
        ]:
            sel = " opt-row--selected" if self.auth_framework == key else ""
            name_cls = "opt-name--selected" if self.auth_framework == key else "opt-name"
            yield Static(
                f"[{name_cls}]🔐 {label}[/{name_cls}]\n[opt-desc]{desc}[/opt-desc]",
                id=f"opt-auth-{key}",
                classes=f"opt-row{sel}",
                markup=True,
            )

        yield Static("Auth App", classes="opt-head")
        skip_sel = " opt-row--selected" if self.skip_auth_app else ""
        skip_name = "opt-name--selected" if self.skip_auth_app else "opt-name"
        yield Static(
            f"[{skip_name}]🚫 Skip authentication app[/{skip_name}]\n"
            f"[opt-desc]Create a project without the auth app scaffold.[/opt-desc]",
            id="opt-skip-auth",
            classes=f"opt-row{skip_sel}",
            markup=True,
        )

        yield Static("Additional", classes="opt-head")
        add_sel = " opt-row--selected" if self.add_pytest else ""
        add_name = "opt-name--selected" if self.add_pytest else "opt-name"
        yield Static(
            f"[{add_name}]✅ pytest-django[/{add_name}]\n[opt-desc]Add pytest-django for testing.[/opt-desc]",
            id="opt-extra-pytest",
            classes=f"opt-row{add_sel}",
            markup=True,
        )

        yield Static("", id="op-summary", markup=True)

    def on_mount(self) -> None:
        self._update_summary()

    def on_click(self, event) -> None:
        widget = event.widget
        for key in ("htmx", "ajax", "jquery"):
            if widget is self.query_one(f"#opt-interactive-{key}", Static):
                self.interactive = key
                break
        for key in ("bootstrap", "tailwind", "none"):
            if widget is self.query_one(f"#opt-css-{key}", Static):
                self.css_framework = key
                break
        for key in ("django", "allauth"):
            if widget is self.query_one(f"#opt-auth-{key}", Static):
                self.skip_auth_app = False
                self.auth_framework = key
                break
        if widget is self.query_one("#opt-skip-auth", Static):
            self.skip_auth_app = not self.skip_auth_app
        if widget is self.query_one("#opt-extra-pytest", Static):
            self.add_pytest = not self.add_pytest

    def watch_interactive(self, val: str) -> None:
        for key in ("htmx", "ajax", "jquery"):
            try:
                row = self.query_one(f"#opt-interactive-{key}", Static)
            except Exception:
                return
            if key == val:
                row.add_class("opt-row--selected")
            else:
                row.remove_class("opt-row--selected")
        self._update_summary()

    def watch_css_framework(self, val: str) -> None:
        for key in ("bootstrap", "tailwind", "none"):
            try:
                row = self.query_one(f"#opt-css-{key}", Static)
            except Exception:
                return
            if key == val:
                row.add_class("opt-row--selected")
            else:
                row.remove_class("opt-row--selected")
        self._update_summary()

    def watch_auth_framework(self, val: str) -> None:
        for key in ("django", "allauth"):
            try:
                row = self.query_one(f"#opt-auth-{key}", Static)
            except Exception:
                return
            if key == val:
                row.add_class("opt-row--selected")
            else:
                row.remove_class("opt-row--selected")
        self._update_summary()

    def watch_add_pytest(self, val: bool) -> None:
        try:
            row = self.query_one("#opt-extra-pytest", Static)
        except Exception:
            return
        if val:
            row.add_class("opt-row--selected")
        else:
            row.remove_class("opt-row--selected")
        self._update_summary()

    def watch_skip_auth_app(self, val: bool) -> None:
        try:
            row = self.query_one("#opt-skip-auth", Static)
        except Exception:
            return
        if val:
            row.add_class("opt-row--selected")
        else:
            row.remove_class("opt-row--selected")
        self._update_summary()
        if val:
            self.auth_framework = "django"

    def _update_summary(self) -> None:
        extras = "pytest-django" if self.add_pytest else "none"
        auth_app = "skipped" if self.skip_auth_app else "enabled"
        text = (
            f"[#3a3a3a]SUMMARY[/]\n"
            f"Interactive: [#44B78B]{self.interactive}[/]\n"
            f"CSS: [#44B78B]{self.css_framework}[/]\n"
            f"Auth: [#44B78B]{self.auth_framework}[/]\n"
            f"Auth App: [#888888]{auth_app}[/]\n"
            f"Extras: [#888888]{extras}[/]"
        )
        self.query_one("#op-summary", Static).update(Text.from_markup(text))


class AuthSetupStep(Vertical):
    DEFAULT_CSS = """
    AuthSetupStep { padding: 2 3; height: auto; }
    #au-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #au-sub   { color: #555555; margin-bottom: 2; }
    .au-row {
        height: auto;
        padding: 1 2;
        background: #111111;
        border: tall #1a1a1a;
        margin-bottom: 1;
    }
    .au-row--selected {
        background: #0a1f14;
        border: tall #44B78B;
    }
    .au-name { color: #888888; text-style: bold; }
    .au-name--selected { color: #44B78B; }
    .au-desc  { color: #3a3a3a; margin-top: 1; }
    """

    custom_user: reactive[bool] = reactive(False)
    run_migrations: reactive[bool] = reactive(True)

    def compose(self) -> ComposeResult:
        yield Static("Auth & Migrations", id="au-title")
        yield Static(
            "Create a custom user model and apply migrations after setup.",
            id="au-sub",
        )

        cu_sel = " au-row--selected" if self.custom_user else ""
        cu_name = "au-name--selected" if self.custom_user else "au-name"
        yield Static(
            f"[{cu_name}]👤 Custom User Model[/{cu_name}]\n"
            f"[au-desc]Create AbstractUser in authentication app and wire settings.[/au-desc]",
            id="au-custom-user",
            classes=f"au-row{cu_sel}",
            markup=True,
        )

        mig_sel = " au-row--selected" if self.run_migrations else ""
        mig_name = "au-name--selected" if self.run_migrations else "au-name"
        yield Static(
            f"[{mig_name}]🗄️ Run Migrations[/{mig_name}]\n"
            f"[au-desc]Apply Django + package migrations after setup.[/au-desc]",
            id="au-migrations",
            classes=f"au-row{mig_sel}",
            markup=True,
        )

    def on_click(self, event) -> None:
        if event.widget is self.query_one("#au-custom-user", Static):
            self.custom_user = not self.custom_user
            if self.custom_user:
                self.run_migrations = True
        elif event.widget is self.query_one("#au-migrations", Static):
            if not self.custom_user:
                self.run_migrations = not self.run_migrations

    def watch_custom_user(self, val: bool) -> None:
        try:
            row = self.query_one("#au-custom-user", Static)
        except Exception:
            return
        if val:
            row.add_class("au-row--selected")
        else:
            row.remove_class("au-row--selected")
        if val:
            self.run_migrations = True

    def watch_run_migrations(self, val: bool) -> None:
        try:
            row = self.query_one("#au-migrations", Static)
        except Exception:
            return
        if val:
            row.add_class("au-row--selected")
        else:
            row.remove_class("au-row--selected")


# ── Wizard nav footer ──────────────────────────────────────────────────────

class WizardNav(Horizontal):
    DEFAULT_CSS = """
    WizardNav {
        height: 5;
        border-top: tall #1a1a1a;
        background: #0f0f0f;
        align: center middle;
        padding: 0 2;
        dock: bottom;
    }
    #wiz-step-label {
        width: 1fr;
        color: #3a3a3a;
        content-align: left middle;
    }
    """

    def __init__(self, step: int, total: int) -> None:
        super().__init__()
        self.step  = step
        self.total = total

    def compose(self) -> ComposeResult:
        yield Static(f"Step {self.step} of {self.total}", id="wiz-step-label")
        if self.step > 1:
            yield Button("← Back", id="wiz-back", classes="btn-wiz-back")
        yield Button(
            "⚡ Create Project" if self.step == self.total else "Next →",
            id="wiz-next",
            classes="btn-wiz-next",
        )


# ── Main wizard screen ─────────────────────────────────────────────────────

class WizardScreen(Screen):
    """4-step project creation wizard."""

    CSS = """
    WizardScreen {
        background: #0a0a0a;
        layout: horizontal;
    }

    #wizard-sidebar { height: 100%; }

    #wizard-main {
        width: 1fr;
        height: 100%;
        background: #0a0a0a;
        layout: vertical;
    }

    #wizard-header {
        height: 3;
        background: #0f0f0f;
        border-bottom: tall #1a1a1a;
        align: left middle;
        padding: 0 2;
    }

    #wizard-scroll {
        height: 1fr;
        overflow-y: auto;
        padding-bottom: 6;
    }
    """

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
    ]

    current_step: reactive[int] = reactive(0)   # 0-indexed

    def compose(self) -> ComposeResult:
        yield StepSidebar(id="wizard-sidebar")
        with Vertical(id="wizard-main"):
            yield Static(
                "[bold #44B78B]Django Manager[/]  [#1e1e1e]› Create Project[/]",
                id="wizard-header",
                markup=True,
            )
            with ScrollableContainer(id="wizard-scroll"):
                yield NameStep(id="step-0")
                yield PythonStep(id="step-1")
                yield DjangoStep(id="step-2")
                yield OptionsStep(id="step-3")
                yield AuthSetupStep(id="step-4")
            yield WizardNav(step=1, total=len(STEPS))

    def on_mount(self) -> None:
        self._apply_responsive()
        self._show_step(0)

    def on_resize(self, event) -> None:  # type: ignore[override]
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        sidebar = self.query_one("#wizard-sidebar")
        width = 18 if self.size.width < 90 else 24
        sidebar.styles.width = width

    # ── Step navigation ───────────────────────────────────────

    def _show_step(self, idx: int) -> None:
        for i in range(len(STEPS)):
            step = self.query_one(f"#step-{i}")
            step.display = (i == idx)

        nav = self.query_one(WizardNav)
        nav.remove()
        self.query_one("#wizard-main").mount(WizardNav(step=idx + 1, total=len(STEPS)))

        sidebar = self.query_one(StepSidebar)
        sidebar.current = idx

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "wiz-next": self._advance()
            case "wiz-back": self._retreat()

    def _advance(self) -> None:
        if self.current_step < len(STEPS) - 1:
            self.current_step += 1
            self._show_step(self.current_step)
        else:
            self._start_install()

    def _retreat(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
            self._show_step(self.current_step)
        else:
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self._retreat()

    # ── Collect form data and go to install ───────────────────

    def _start_install(self) -> None:
        name_input = self.query_one("#project-name", Input).value.strip() or "my_project"
        loc_input  = self.query_one("#project-location", Input).value.strip() or "~/projects/"
        python_ver = self.query_one(PythonStep).selected
        django_ver = self.query_one(DjangoStep).selected
        opts = self.query_one(OptionsStep)
        auth_step = self.query_one(AuthSetupStep)

        packages = ["django"]
        if opts.interactive == "htmx":
            packages.append("django-htmx")
        if opts.auth_framework == "allauth":
            packages.append("django-allauth")
        if opts.add_pytest:
            packages.append("pytest-django")

        cfg = ProjectConfig(
            name         = name_input,
            location     = Path(loc_input).expanduser(),
            python_ver   = python_ver,
            django_ver   = django_ver,
            starter_pack = "options",
            packages     = packages,
            interactive  = opts.interactive,
            css_framework= opts.css_framework,
            auth_framework= opts.auth_framework,
            add_pytest   = opts.add_pytest,
            skip_auth_app= opts.skip_auth_app,
            custom_user  = auth_step.custom_user,
            run_migrations = auth_step.run_migrations,
        )

        from .install import InstallScreen
        self.app.switch_screen(InstallScreen(cfg=cfg))
