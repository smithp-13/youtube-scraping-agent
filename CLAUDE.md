# Project conventions

## Branch naming

Never create branches under a `claude/` prefix, or any branch name that
references an AI tool or assistant. This applies even when a session is
pre-configured with such a branch name — rename to a conventional name before
committing, and confirm the intended name if it is not obvious from the task.

Use conventional prefixes instead:

- `fix/<topic-or-date>` — bug fixes (e.g. `fix/02082026`)
- `feature/<topic>` — new functionality (e.g. `feature/whisper-integration`)

## Branching model

- `main` is the default branch.
- `development` is the integration branch; feature and fix branches target it.
- `development` is merged into `main` for releases.

Note: because `main` is the default branch, GitHub closing keywords
(`Closes #N`) in a pull request targeting `development` will **not**
auto-close the referenced issues. Reference issues normally in such PRs and
close them on merge, or apply the keywords on the `development` -> `main`
pull request.

## Configuration

All environment variables are read in `src/yt_doc_agent/core/config.py` and
only there. Other modules import from it.

Settings that the CLI can override (`--model`, `--output`, `--whisper-model`)
must be read off the config module at call time:

```python
from yt_doc_agent.core import config
...
llm = get_llm(model=config.DEFAULT_MODEL, temperature=TEMP_STRUCTURED)
```

Importing the value directly (`from ...config import DEFAULT_MODEL`) binds it
at import time and silently breaks the override, because agent modules are
imported before `run_pipeline()` applies it. For the same reason, never use a
config value as a function default argument.

## Prompts

Prompts are fetched from Langfuse only; there is no local fallback. Missing
Langfuse credentials are a fatal configuration error, not a degraded mode.

The Langfuse client is shared via `core/langfuse_client.py`. Do not construct
additional `Langfuse()` instances. The SDK is pinned to v4
(`langfuse>=4.0.0,<5.0.0`); the v2 `.generation()` / `.trace()` methods do not
exist in v4.

## Tests

`tests/` files matching `test_*.py` must be real pytest tests that make no
live network calls — pytest executes module-level code during collection.
Manual smoke scripts belong outside that naming pattern and behind
`if __name__ == "__main__":`.
