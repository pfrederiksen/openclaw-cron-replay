# openclaw-cron-replay

`openclaw-cron-replay` is a small debugging CLI for replaying an OpenClaw cron job locally against saved job configs, prompts, payloads, result files, and optional prior run metadata.

It helps answer:

- Which prompt or payload would this cron run use?
- What user-visible content would be derived from a saved result?
- Would the cron announce, suppress, or deliver a final message?
- Are there contradictions like `NO_REPLY` plus generated content?

It is intentionally focused on cron debugging and replay. It is not a full OpenClaw runtime simulator and it does not perform real delivery.

## Install

From source:

```bash
python -m pip install -e ".[dev]"
```

From PyPI after release:

```bash
python -m pip install openclaw-cron-replay
```

From Homebrew after release:

```bash
brew tap pfrederiksen/tap
brew install openclaw-cron-replay
```

## Examples

Replay a job from `jobs.json`:

```bash
openclaw-cron-replay --job 429c62e0-2b1f-4179-bac3-792f405d09ae
```

Replay a job using a saved result file:

```bash
openclaw-cron-replay \
  --job 9afc7d6c-64ab-45a2-9e17-da069b3181d9 \
  --result /tmp/news_digest_result.json
```

Resolve a run id and render Markdown:

```bash
openclaw-cron-replay --from-run manual:429c62e0-2b1f-4179-bac3-792f405d09ae --markdown
```

Use explicit prompt and payload text files:

```bash
openclaw-cron-replay \
  --job 429c62e0-2b1f-4179-bac3-792f405d09ae \
  --prompt fixtures/prompts/news_digest.txt \
  --payload fixtures/payloads/news_digest_payload.txt
```

Emit machine-readable JSON:

```bash
openclaw-cron-replay --job no-reply-job --result fixtures/results/no_reply_with_content.json --json
```

Compare two job configs:

```bash
openclaw-cron-replay --compare fixtures/jobs.before.json fixtures/jobs.after.json
```

Diff replay outputs before and after a prompt change:

```bash
openclaw-cron-replay \
  --job news-digest \
  --prompt fixtures/prompts/news_digest.txt \
  --diff-prompt fixtures/prompts/news_digest_changed.txt
```

## Inputs

The CLI accepts:

- `--job`: job id found in a jobs file.
- `--jobs`: path to a jobs JSON file. Defaults to `jobs.json`.
- `--result`: saved result JSON file.
- `--prompt`: saved prompt text file.
- `--payload`: saved payload text file.
- `--metadata`: optional prior run metadata JSON file.
- `--from-run`: optional run id. `manual:<job-id>` resolves the job id when `--job` is omitted.

`jobs.json` may be:

- a list of job objects,
- an object with a `jobs` list,
- an object whose keys are job ids and values are job objects.

The parser is intentionally tolerant because real cron config snapshots vary.

## Output

The replay report includes:

- resolved prompt and payload,
- derived user-visible output,
- delivery mode interpretation,
- likely final message text,
- warnings about risky patterns.

Supported renderers:

- default terminal output,
- `--json`,
- `--markdown`.

## What Is Simulated

- Job config resolution.
- Prompt and payload selection from files, job fields, or metadata.
- Result-file output extraction from common fields such as `content`, `text`, `message`, `output`, `reply`, and `markdown`.
- Delivery interpretation for announce, text-return, silent, suppressed, and `NO_REPLY` patterns.
- Likely final message text.
- Risk warnings.

## What Is Not Simulated

- Network calls.
- Real OpenClaw agent execution.
- Scheduler timing.
- Authentication, authorization, or secrets.
- Webhook, Slack, email, or other real delivery.
- Durable runtime state mutation.

## Fixtures

Sample cron patterns live under `fixtures/`:

- `fixtures/jobs.json`
- `fixtures/results/*.json`
- `fixtures/prompts/*.txt`
- `fixtures/payloads/*.txt`
- `fixtures/metadata/*.json`

These are synthetic fixtures meant to represent common cron debugging cases.

## Release

This repo includes GitHub Actions for:

- tests on pull requests and main,
- package build checks,
- tag-based PyPI publishing,
- tag-based Homebrew tap update.

Use semantic version tags:

```bash
git tag v0.1.0
git push origin v0.1.0
```

For PyPI, configure trusted publishing for this repository or add a `PYPI_API_TOKEN` secret and adapt the workflow. Do not commit PyPI tokens.

For Homebrew, configure `HOMEBREW_TAP_TOKEN` with access to `pfrederiksen/homebrew-tap`.
