# Django Manager

> The modern Django control centre — TUI + uv + Rich

Django Manager is a unified terminal tool that replaces the scattered
`python manage.py`, `pip install`, `virtualenv` workflow with a single,
beautiful interface.

---

## Install

```bash
pip install django-manager
# or
uv add django-manager
```

## Run

```bash
django-manager
# or
dm
```

---

## What it does

**Create a project** — interactive wizard picks Python version, Django version,
and starter pack. uv handles the venv, packages, and lockfile automatically.

**Run Django commands** — type `django migrate`, `django runserver`,
`django makemigrations` directly in the input bar. Output is rendered
with colour, badges, and structured formatting.

**Server panel** — `django runserver` runs in its own panel at the top of
the dashboard. Request logs are colour-coded by HTTP method and status code.
The command output panel below it stays free for other commands — no split
terminal needed.

**Manager commands** — `manager docs`, `manager add <pkg>`,
`manager update`, `manager lock`, `manager env`.

---

## Starter Packs (v0.1)

| Pack | Packages |
|------|----------|
| Django HTMX Stack | django + django-htmx |

More packs in v0.2: DRF, Allauth, Full Stack.

---

## Tech stack

| Layer | Library |
|-------|---------|
| TUI engine | [Textual](https://github.com/Textualize/textual) |
| Styled output | [Rich](https://github.com/Textualize/rich) |
| Env + packages | [uv](https://github.com/astral-sh/uv) |
| CLI routing | [Click](https://click.palletsprojects.com/) |
| Distribution | PyPI + Nuitka binary |

---

## Command reference

### Django commands
```
django runserver
django migrate
django makemigrations
django shell
django collectstatic
django startapp <name>
django <any management command>
```

### Manager commands
```
manager create
manager open
manager docs
manager add <package>
manager update
manager lock
manager env
```

---

## License

MIT
