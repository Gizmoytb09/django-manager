"""
Django Manager — Create Project Wizard
Steps: 1 Name → 2 Python → 3 Django → 4 Starter Pack → Install
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
    APP_VERSION, DJANGO_VERSIONS, PYTHON_VERSIONS, STARTER_PACKS,
)
from ..core.operations import ProjectConfig


# ── Sidebar step list ──────────────────────────────────────────────────────

STEPS = [
    "Project Name",
    "Python Version",
    "Django Version",
    "Starter Pack",
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


class StarterPackStep(Vertical):
    DEFAULT_CSS = """
    StarterPackStep { padding: 2 3; height: auto; }
    #sp-title { color: #44B78B; text-style: bold; margin-bottom: 1; }
    #sp-sub   { color: #555555; margin-bottom: 2; }

    .pack-row {
        height: auto;
        padding: 1 2;
        background: #111111;
        border: tall #1a1a1a;
        margin-bottom: 1;
    }
    .pack-row--selected {
        background: #0a1f14;
        border: tall #44B78B;
    }
    .pack-row--disabled {
        background: #0a0a0a;
        border: tall #111111;
        opacity: 0.4;
    }
    .pack-name { color: #888888; text-style: bold; }
    .pack-name--selected { color: #44B78B; }
    .pack-desc  { color: #3a3a3a; margin-top: 1; }
    .pack-tags  { color: #1e6e42; margin-top: 1; }
    .pack-soon  { color: #1e1e1e; }

    #sp-summary {
        background: #0f0f0f; border: tall #1a1a1a;
        padding: 1 2; height: auto; margin-top: 1;
    }
    """

    selected_pack: reactive[Optional[str]] = reactive("htmx")

    def compose(self) -> ComposeResult:
        yield Static("Starter Packs", id="sp-title")
        yield Static("Select a pack to bootstrap your project with curated packages.", id="sp-sub")

        for pack in STARTER_PACKS:
            sel    = " pack-row--selected" if pack["id"] == "htmx" else ""
            dis    = " pack-row--disabled" if not pack["available"] else ""
            name_c = "pack-name--selected" if pack["id"] == "htmx" else "pack-name"
            tags   = "  ".join(pack["tags"])
            soon   = "" if pack["available"] else "  [COMING V2]"

            yield Static(
                f"[{name_c}]{pack['icon']} {pack['name']}[/{name_c}]{soon}\n"
                f"[pack-desc]{pack['desc']}[/pack-desc]\n"
                f"[#1e6e42]{tags}[/]",
                id=f"pack-{pack['id']}",
                classes=f"pack-row{sel}{dis}",
                markup=True,
            )

        yield Static("", id="sp-summary", markup=True)

    def on_mount(self) -> None:
        self._update_summary()

    def on_click(self, event) -> None:
        for pack in STARTER_PACKS:
            if not pack["available"]:
                continue
            row = self.query_one(f"#pack-{pack['id']}", Static)
            if event.widget is row:
                if self.selected_pack == pack["id"]:
                    self.selected_pack = None
                else:
                    self.selected_pack = pack["id"]
                break

    def watch_selected_pack(self, val: Optional[str]) -> None:
        for pack in STARTER_PACKS:
            if not pack["available"]:
                continue
            row = self.query_one(f"#pack-{pack['id']}", Static)
            if pack["id"] == val:
                row.add_class("pack-row--selected")
                row.remove_class("pack-row")
            else:
                row.remove_class("pack-row--selected")
        self._update_summary()

    def _update_summary(self) -> None:
        pack = next((p for p in STARTER_PACKS if p["id"] == self.selected_pack), None)
        if pack:
            pkgs = ", ".join(pack["packages"])
            text = (
                f"[#3a3a3a]SUMMARY[/]\n"
                f"Pack: [#44B78B]{pack['name']}[/]\n"
                f"Packages: [#888888]{pkgs}[/]"
            )
        else:
            text = "[#3a3a3a]No starter pack selected — only Django will be installed.[/]"
        self.query_one("#sp-summary", Static).update(Text.from_markup(text))


# ── Wizard nav footer ──────────────────────────────────────────────────────

class WizardNav(Horizontal):
    DEFAULT_CSS = """
    WizardNav {
        height: 5;
        border-top: tall #1a1a1a;
        background: #0f0f0f;
        align: right middle;
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
                yield StarterPackStep(id="step-3")
            yield WizardNav(step=1, total=4)

    def on_mount(self) -> None:
        self._show_step(0)

    # ── Step navigation ───────────────────────────────────────

    def _show_step(self, idx: int) -> None:
        for i in range(4):
            step = self.query_one(f"#step-{i}")
            step.display = (i == idx)

        nav = self.query_one(WizardNav)
        nav.remove()
        self.query_one("#wizard-main").mount(WizardNav(step=idx + 1, total=4))

        sidebar = self.query_one(StepSidebar)
        sidebar.current = idx

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "wiz-next": self._advance()
            case "wiz-back": self._retreat()

    def _advance(self) -> None:
        if self.current_step < 3:
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
        pack_id    = self.query_one(StarterPackStep).selected_pack

        from ..core.config import STARTER_PACKS
        pack = next((p for p in STARTER_PACKS if p["id"] == pack_id), None)
        packages = pack["packages"] if pack else ["django"]

        cfg = ProjectConfig(
            name         = name_input,
            location     = Path(loc_input).expanduser(),
            python_ver   = python_ver,
            django_ver   = django_ver,
            starter_pack = pack_id or "none",
            packages     = packages,
        )

        from .install import InstallScreen
        self.app.switch_screen(InstallScreen(cfg=cfg))
