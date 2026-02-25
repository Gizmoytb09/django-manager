"""
Django Manager — App settings (user preferences).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

SETTINGS_PATH = Path.home() / ".django_manager.json"


@dataclass
class AppSettings:
    layout_mode: str = "split"  # "split" | "tabs"
    sidebar_compact: bool = False
    auto_switch_command: bool = True
    show_project_path: bool = True
    show_server_timestamps: bool = True
    show_server_levels: bool = True
    show_running_badge: bool = True
    show_command_welcome: bool = True
    server_auto_scroll: bool = True
    command_auto_scroll: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        layout = data.get("layout_mode", "split")
        if layout not in ("split", "tabs"):
            layout = "split"
        return cls(
            layout_mode=layout,
            sidebar_compact=bool(data.get("sidebar_compact", False)),
            auto_switch_command=bool(data.get("auto_switch_command", True)),
            show_project_path=bool(data.get("show_project_path", True)),
            show_server_timestamps=bool(data.get("show_server_timestamps", True)),
            show_server_levels=bool(data.get("show_server_levels", True)),
            show_running_badge=bool(data.get("show_running_badge", True)),
            show_command_welcome=bool(data.get("show_command_welcome", True)),
            server_auto_scroll=bool(data.get("server_auto_scroll", True)),
            command_auto_scroll=bool(data.get("command_auto_scroll", True)),
        )


def load_settings() -> AppSettings:
    try:
        raw = SETTINGS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return AppSettings.from_dict(data)
    except Exception:
        pass
    return AppSettings()


def save_settings(settings: AppSettings) -> None:
    SETTINGS_PATH.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
