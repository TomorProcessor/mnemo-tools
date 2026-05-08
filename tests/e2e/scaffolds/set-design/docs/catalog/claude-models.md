# Claude Models

The model select in set-design's settings exposes three named options. Each maps to a concrete claude-code model identifier and has a per-1M-token cost reference used by the cost-display feature.

This file is the authoritative reference. The orchestrator (F08) maps `config.model` enum → CLI flag.

## Model table

| Display name | `config.model` | CLI `--model` argument | Per-1M input | Per-1M output | When to choose |
|---|---|---|---|---|---|
| Opus | `opus` | `claude-opus-4-7` | $15.00 | $75.00 | Default — highest quality, complex layouts, multi-component refactors |
| Sonnet | `sonnet` | `claude-sonnet-4-6` | $3.00 | $15.00 | Faster, cheaper iterations on simple changes; good for tweaks |
| Haiku | `haiku` | `claude-haiku-4-5-20251001` | $1.00 | $5.00 | Fastest; suitable for tiny visual edits and quick exploration |

Cost values are illustrative guidelines for the cost-display feature. Real billing comes from the Anthropic API; these numbers are approximate and SHOULD be revised when Anthropic publishes updates.

## How `config.model` is used

```
Brain reads config.model         →  resolve to CLI string via the table above
                                 →  pass to `claude -p --model <full-id>`
Cost calculation per turn:       (input_tokens × per_1M_input + output_tokens × per_1M_output) / 1_000_000
                                 input/output tokens come from the `result` event in stream-json
```

When the model select is changed mid-session:

- The new model is used for the **next** turn.
- The current claude session is preserved (`--resume <session_id>` still works across model switches).
- The status bar's cost display continues accumulating; cost-per-turn footer reflects the active model at the time of that turn.

## Default

`opus` is the default for new targets. Justified because:
- Quality matters most for design work.
- Cost is bounded per turn (typical UI edits: 2k–8k output tokens → $0.15–$0.60).
- A single `auto_commit` revert is free, so quality > volume.

Users on tight budgets may switch to `sonnet` or `haiku` from settings.

## Future models

When new claude versions ship, this catalog file is the change-target. Adding `Sonnet 4.7` etc. = one row in the table + one new enum value in `config.model`. No other code changes if the per-1M numbers and CLI string format hold.

## Test fixtures

E2E tests against the mock-claude shim use `model: "opus"` by default. Tests covering model selection (settings page) iterate through all three values.
