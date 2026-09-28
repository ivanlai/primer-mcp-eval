# Scripts

Standard library only; run with `python3`. Pinned versions and limits live in `eval.toml`.

- `validate_scenarios.py`: checks every scenario mechanically (see `scenarios/README.md`).
- `run_eval.py`: runs scenarios as isolated headless Claude Code sessions into `runs/<batch>/…` (gitignored). Real runs need `ANTHROPIC_API_KEY`, because each session gets an empty `HOME` with no stored login. Start with `--dry-run`.
- `score.py`: scores saved runs against the ADR-004 metrics (the rules are in its docstring) and writes `results/<batch>/runs.csv` and `summary.md`.

Tests for the scripts use a stub `claude` and make no API calls:

```
uv run --with pytest --no-project pytest -p no:cacheprovider tests
```
