"""
Django Manager — App root
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult

from .core.settings import load_settings
from .screens import HomeScreen



class DjangoManagerApp(App):
    """Django Manager — The modern Django control centre."""

    TITLE    = "Django Manager"
    CSS_PATH = Path(__file__).parent / "app.css"

    def on_mount(self) -> None:
        self.settings = load_settings()
        self.push_screen(HomeScreen())


def run() -> None:
    DjangoManagerApp().run()


if __name__ == "__main__":
    run()
