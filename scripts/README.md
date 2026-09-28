# Scripts

Standard library only; run with `python3`. Pinned versions and limits live in `eval.toml`.

- `validate_scenarios.py`: checks every scenario mechanically (see `scenarios/README.md`).
- `run_eval.py`: runs scenarios as isolated headless Claude Code sessions into `runs/<batch>/…` (gitignored). Each session gets an empty `HOME` with no stored login, so real runs need a credential passed in: a subscription token from `claude setup-token`, saved in `~/.config/primer-mcp-eval/oauth-token` (or `CLAUDE_CODE_OAUTH_TOKEN`), or `ANTHROPIC_API_KEY`. Start with `--dry-run`; use `--redo-failed` after an interruption such as a usage limit.
- `score.py`: scores saved runs against the ADR-004 metrics (the rules are in its docstring) and writes `results/<batch>/runs.csv` and `summary.md`.

Tests for the scripts use a stub `claude` and make no API calls:

```
uv run --with pytest --no-project pytest -p no:cacheprovider tests
```
