> [!WARNING]
> ## ⚠️ v0.1 — BETA RELEASE
> **This is an early beta. Bugs, crashes, rough edges, and missing features are expected.**
> Proceed with curiosity — and maybe a backup. If something breaks, [open an issue](https://github.com/Gizmoytb09/django-manager/issues) and help shape what this becomes.
> **Not recommended for production use yet.**

---

# 🎛️ Django Manager
### *The modern Django control centre — TUI · uv · Rich*

> **Have you ever stopped mid-project to wonder why managing a Django app still feels like running commands blindfolded?**
> Why do you need five separate terminal tabs just to run a server, manage packages, check migrations, and keep your virtualenv in order?
> **What if all of that — every single piece — lived in one beautiful, unified interface?**

Django Manager is the answer to the question you've been asking every time you type `python manage.py` into yet another terminal window. It is a **fully unified, terminal-native control centre** for Django development — combining project creation, dependency management, server monitoring, and command execution into a single, strikingly beautiful TUI powered by **Textual**, **Rich**, and **uv**.

**No more scattered workflows. No more split terminals. No more forgotten virtualenvs.**

---

## 🚀 Why Django Manager Exists

Ask yourself honestly: **how much time do you lose every week just *setting up* Django projects?** Choosing a Python version, creating a virtual environment, installing packages, generating a `requirements.txt` or lockfile, running the first migration — it's repetitive, error-prone, and frankly, boring.

And once you're *in* a project? You're context-switching between terminals constantly. The dev server runs in one tab. You're running `makemigrations` in another. You're installing a new package in a third. Your shell history is a graveyard of half-remembered `manage.py` invocations.

**Django Manager was built to make all of that disappear.**

---

## 📦 Installation

Getting started is as simple as it gets. **Why should setup ever be the hard part?**

```bash
# Via pip
pip install django-manager

# Via uv (recommended)
uv add django-manager
```

---

## ▶️ Running

```bash
# Full command
django-manager

# Short alias
dm
```

**One command. That's it.** The entire dashboard opens instantly, ready to go.

---

## ✨ What It Actually Does

### 🧙 **Project Creation Wizard**

> *What if creating a new Django project felt less like surgery and more like answering a few questions?*

The interactive creation wizard guides you through every decision — **Python version**, **Django version**, **starter pack** — and handles everything else automatically. Under the hood, **uv** creates your virtual environment, installs all packages, and generates a clean lockfile. You walk away with a fully configured, ready-to-run project in seconds.

---

### ⚡ **Django Command Execution**

> *Why should running a migration feel any different from typing a search query?*

Type Django commands **directly into the input bar**. No `python manage.py` prefix. No activating a virtualenv. Just the command, clean and fast.

```
django migrate
django runserver
django makemigrations
django shell
django collectstatic
django startapp myapp
```

**Output is rendered beautifully** — colour-coded, structured, with badges and formatted panels. Error messages that used to scroll past you in a wall of grey text are now highlighted, readable, and impossible to miss.

---

### 🖥️ **Live Server Panel**

> *Have you ever wished your dev server logs were actually *readable*?*

`django runserver` runs in its **own dedicated panel** at the top of the dashboard. Request logs are **colour-coded by HTTP method and status code** — GET, POST, 404, 500 — all instantly distinguishable at a glance. The command output panel beneath it stays completely free for all your other work.

**No split terminal needed. No juggling windows. The layout just works.**

---

### 🛠️ **Manager Commands**

Beyond Django itself, Django Manager gives you first-class control over your environment and dependencies:

| Command | What It Does |
|---|---|
| `manager create` | Launch the project creation wizard |
| `manager open` | Open an existing project |
| `manager docs` | Open Django documentation |
| `manager add <pkg>` | Add a new package via uv |
| `manager update` | Update all dependencies |
| `manager lock` | Regenerate the lockfile |
| `manager env` | Inspect the virtual environment |

> *When was the last time managing your Python environment felt this frictionless?*

---

## 📦 Starter Packs

**Why reinvent the wheel on every new project?** Starter packs give you a curated, battle-tested foundation from day one.

| Pack | Included Packages | Status |
|---|---|---|
| **Django HTMX Stack** | `django` + `django-htmx` | ✅ Available in v0.1 |
| **Django REST Framework** | `django` + `djangorestframework` | 🔜 Coming in v0.2 |
| **Full Auth Stack** | `django` + `django-allauth` | 🔜 Coming in v0.2 |
| **Full Stack** | `django` + `htmx` + `tailwind` | 🔜 Coming in v0.2 |

> *More packs are actively being built. What stack do* you *reach for on day one?*

---

## 🏗️ Tech Stack

Every layer of Django Manager was chosen deliberately. **Because if you're going to build a developer tool, shouldn't it be built on the best tools available?**

| Layer | Library | Why It Was Chosen |
|---|---|---|
| **TUI Engine** | [Textual](https://github.com/Textualize/textual) | The gold standard for terminal UI in Python |
| **Styled Output** | [Rich](https://github.com/Textualize/rich) | Beautiful, expressive terminal rendering |
| **Env + Packages** | [uv](https://github.com/astral-sh/uv) | Blazing-fast, modern Python package management |
| **CLI Routing** | [Click](https://click.palletsprojects.com/) | Clean, composable command-line interface design |
| **Distribution** | PyPI + Nuitka binary | Install anywhere, run as a standalone binary |

---

## 📖 Full Command Reference

### Django Commands

Run any Django management command directly — no prefix, no activation, no friction:

```
django runserver
django migrate
django makemigrations
django shell
django collectstatic
django startapp <name>
django <any management command>
```

### Manager Commands

Control your environment, dependencies, and project lifecycle:

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

## 🗺️ Roadmap

**This is v0.1. There is so much more coming.**

- `v0.2` — More starter packs (DRF, Allauth, Full Stack), improved server panel, plugin system
- `v0.3` — Multi-project dashboard, environment comparison, dependency audit
- `v1.0` — Stable API, full documentation site, binary distribution for all platforms

> *What would make Django Manager indispensable for your workflow? Open an issue and tell us.*

---

## 🤝 Contributing

Django Manager is early, open, and hungry for feedback. **Found a bug? Have an idea? Think something should work differently?**

Issues, pull requests, and opinionated feedback are all deeply welcome. This tool is being built in public, for the Django community, by people who are tired of the same old workflow.

---

## 📄 License

**MIT** — free to use, fork, extend, and ship.

---

*Built with obsessive attention to developer experience. Powered by Textual, Rich, uv, and Click.*
*Django Manager v0.1 Beta — the first version of something that aims to be the last Django tool you reach for.*
