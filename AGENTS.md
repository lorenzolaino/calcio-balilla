# Repository Guidelines

## Project Structure & Module Organization

- `app.py` is the Streamlit entrypoint and contains the UI flow.
- `models.py` holds database-backed application logic and caching helpers.
- `db.py` creates the SQLAlchemy engine and initializes the schema.
- `scoring.py` contains the pure Elo and match-comparison logic.
- `tests/` contains `unittest` test cases.
- `docs/` holds design notes and refactor plans such as `docs/REFRACTOR_ROADMAP.md`.

Keep UI code in `app.py` or small UI helpers, pure rules in `scoring.py`, and SQL/database access in `models.py` or `db.py`.

## Build, Test, and Development Commands

- `pip install -r requirements.txt` installs the Python dependencies.
- `streamlit run app.py` starts the app locally.
- `python3 -m unittest discover -s tests` runs the full test suite.

The app expects `DATABASE_URL` to point to PostgreSQL before startup.

## Coding Style & Naming Conventions

- Use 4-space indentation and standard PEP 8 Python style.
- Prefer `snake_case` for functions, variables, and file names.
- Use `UPPER_CASE` for constants such as `CURRENT_VERSION` or thresholds.
- Keep SQL explicit and localized; avoid spreading query strings across UI code.
- Add short comments only where logic is non-obvious.

## Testing Guidelines

- Tests use `unittest` with `tests/test_*.py` naming.
- Prefer unit tests for pure logic in `scoring.py`.
- When touching database behavior, keep tests focused on the SQL contract and mocked engine interactions.
- Run `python3 -m unittest discover -s tests` before opening a PR.

## Commit & Pull Request Guidelines

- Commit messages in this repo are short, imperative, and action-oriented, for example: `Added tests`, `Fix mobile bar`, `Change UI`.
- Keep commits scoped to one logical change.
- PRs should explain what changed, why it changed, and how it was verified.
- Include screenshots or screen recordings when changing Streamlit UI behavior.

## Security & Configuration Tips

- Do not commit secrets or database URLs.
- Set `DATABASE_URL` locally before running the app or tests.
- Treat password handling carefully; `models.py` currently hashes passwords directly and is a good candidate for future hardening.
