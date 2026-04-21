from __future__ import annotations

from dataclasses import asdict, dataclass, field
from difflib import unified_diff
import json
from pathlib import Path
from typing import Any


TEXT_RESULT_KEYS = (
    "final_message",
    "message",
    "content",
    "text",
    "output",
    "reply",
    "markdown",
    "summary",
    "body",
)

PROMPT_KEYS = ("prompt", "system_prompt", "user_prompt", "instructions")
PAYLOAD_KEYS = ("payload", "input", "request", "body")
DELIVERY_KEYS = ("delivery_mode", "deliveryMode", "mode", "delivery", "response_mode")


@dataclass(slots=True)
class DeliveryInterpretation:
    mode: str
    announced: bool
    suppressed: bool
    reason: str


@dataclass(slots=True)
class ReplayReport:
    job_id: str | None
    job_name: str | None
    source_files: dict[str, str] = field(default_factory=dict)
    prompt: str = ""
    payload: str = ""
    derived_output: str = ""
    delivery: DeliveryInterpretation | None = None
    final_message: str = ""
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    job: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def replay(
    *,
    job_id: str | None = None,
    jobs_path: Path | None = None,
    result_path: Path | None = None,
    prompt_path: Path | None = None,
    payload_path: Path | None = None,
    metadata_path: Path | None = None,
    from_run: str | None = None,
) -> ReplayReport:
    resolved_job_id = job_id or job_id_from_run(from_run)
    source_files: dict[str, str] = {}

    jobs: list[dict[str, Any]] = []
    if jobs_path and jobs_path.exists():
        jobs = load_jobs(jobs_path)
        source_files["jobs"] = str(jobs_path)
    elif jobs_path and resolved_job_id:
        raise FileNotFoundError(f"jobs file not found: {jobs_path}")

    job = find_job(jobs, resolved_job_id) if resolved_job_id else {}
    metadata = load_json_object(metadata_path) if metadata_path else {}
    if metadata_path:
        source_files["metadata"] = str(metadata_path)

    result = load_json_object(result_path) if result_path else {}
    if result_path:
        source_files["result"] = str(result_path)

    prompt = read_text(prompt_path) if prompt_path else first_text(job, PROMPT_KEYS)
    if not prompt:
        prompt = first_text(metadata, PROMPT_KEYS)
    if prompt_path:
        source_files["prompt"] = str(prompt_path)

    payload = read_text(payload_path) if payload_path else first_text(job, PAYLOAD_KEYS)
    if not payload:
        payload = first_text(metadata, PAYLOAD_KEYS)
    if payload_path:
        source_files["payload"] = str(payload_path)

    derived_output = derive_output(result, job, metadata)
    delivery = interpret_delivery(job, result, derived_output)
    final_message = derive_final_message(derived_output, delivery, job, result)
    warnings = collect_warnings(job, result, prompt, payload, derived_output, delivery)

    return ReplayReport(
        job_id=resolved_job_id or stringify(job.get("id")) or None,
        job_name=stringify(job.get("name")) or stringify(job.get("title")) or None,
        source_files=source_files,
        prompt=prompt,
        payload=payload,
        derived_output=derived_output,
        delivery=delivery,
        final_message=final_message,
        warnings=warnings,
        metadata=metadata,
        job=job,
    )


def load_json_object(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, dict):
        return data
    return {"value": data}


def load_jobs(path: Path) -> list[dict[str, Any]]:
    data = load_json_object(path)
    raw_jobs: Any
    if isinstance(data.get("jobs"), list):
        raw_jobs = data["jobs"]
    elif all(isinstance(value, dict) for value in data.values()):
        raw_jobs = [{"id": key, **value} for key, value in data.items()]
    else:
        raw_jobs = data.get("value", [])

    if isinstance(raw_jobs, dict):
        raw_jobs = [{"id": key, **value} for key, value in raw_jobs.items()]
    if not isinstance(raw_jobs, list):
        raise ValueError(f"unsupported jobs JSON shape in {path}")

    jobs = []
    for item in raw_jobs:
        if not isinstance(item, dict):
            continue
        jobs.append(item)
    return jobs


def find_job(jobs: list[dict[str, Any]], job_id: str | None) -> dict[str, Any]:
    for job in jobs:
        if stringify(job.get("id")) == job_id or stringify(job.get("job_id")) == job_id:
            return job
    if job_id:
        raise KeyError(f"job id not found: {job_id}")
    return {}


def job_id_from_run(from_run: str | None) -> str | None:
    if not from_run:
        return None
    if from_run.startswith("manual:"):
        return from_run.split(":", 1)[1]
    return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def first_text(*objects_and_keys: Any) -> str:
    if len(objects_and_keys) == 2 and isinstance(objects_and_keys[1], tuple):
        obj, keys = objects_and_keys
        return first_text_value(obj, keys)
    for obj in objects_and_keys:
        value = first_text_value(obj, TEXT_RESULT_KEYS)
        if value:
            return value
    return ""


def first_text_value(obj: Any, keys: tuple[str, ...]) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in keys:
        value = obj.get(key)
        text = stringify(value)
        if text:
            return text
    return ""


def derive_output(*objects: dict[str, Any]) -> str:
    for obj in objects:
        text = extract_text(obj)
        if text:
            return text
    return ""


def extract_text(value: Any) -> str:
    direct = stringify(value)
    if direct and not isinstance(value, dict):
        return direct

    if isinstance(value, dict):
        for key in TEXT_RESULT_KEYS:
            text = stringify(value.get(key))
            if text:
                return text
        for nested_key in ("result", "data", "response", "agent", "completion"):
            text = extract_text(value.get(nested_key))
            if text:
                return text
        choices = value.get("choices")
        if isinstance(choices, list) and choices:
            text = extract_text(choices[0])
            if text:
                return text
    if isinstance(value, list):
        pieces = [extract_text(item) for item in value]
        pieces = [piece for piece in pieces if piece]
        return "\n".join(pieces)
    return ""


def interpret_delivery(
    job: dict[str, Any],
    result: dict[str, Any],
    derived_output: str,
) -> DeliveryInterpretation:
    mode = normalized_delivery_mode(job, result)
    if mode == "no_reply":
        return DeliveryInterpretation(
            mode="NO_REPLY",
            announced=False,
            suppressed=True,
            reason="delivery mode explicitly suppresses replies",
        )
    if mode in {"silent", "suppress", "suppressed"}:
        return DeliveryInterpretation(
            mode="silent",
            announced=False,
            suppressed=True,
            reason="job is configured for silent delivery",
        )
    if mode in {"announce", "announcement"}:
        return DeliveryInterpretation(
            mode="announce",
            announced=bool(derived_output),
            suppressed=False,
            reason="job is configured to announce user-visible output",
        )
    if mode in {"text_return", "text-return", "return_text", "return-text"}:
        return DeliveryInterpretation(
            mode="text-return",
            announced=bool(derived_output),
            suppressed=False,
            reason="job returns text as the visible cron result",
        )
    if truthy(job.get("announce")) or truthy(result.get("announce")):
        return DeliveryInterpretation(
            mode="announce",
            announced=bool(derived_output),
            suppressed=False,
            reason="announce flag is enabled",
        )
    if truthy(job.get("no_reply")) or truthy(job.get("noReply")):
        return DeliveryInterpretation(
            mode="NO_REPLY",
            announced=False,
            suppressed=True,
            reason="job no_reply flag is enabled",
        )
    if derived_output:
        return DeliveryInterpretation(
            mode="implicit-text",
            announced=True,
            suppressed=False,
            reason="no explicit delivery mode found; derived output would likely be visible",
        )
    return DeliveryInterpretation(
        mode="empty",
        announced=False,
        suppressed=True,
        reason="no user-visible output was derived",
    )


def normalized_delivery_mode(job: dict[str, Any], result: dict[str, Any]) -> str:
    for source in (result, job):
        for key in DELIVERY_KEYS:
            value = stringify(source.get(key)).lower().strip()
            if value:
                return value.replace(" ", "_")
    return ""


def derive_final_message(
    derived_output: str,
    delivery: DeliveryInterpretation,
    job: dict[str, Any],
    result: dict[str, Any],
) -> str:
    explicit = stringify(result.get("final_message")) or stringify(job.get("final_message"))
    if delivery.suppressed:
        return ""
    return explicit or derived_output


def collect_warnings(
    job: dict[str, Any],
    result: dict[str, Any],
    prompt: str,
    payload: str,
    derived_output: str,
    delivery: DeliveryInterpretation,
) -> list[str]:
    warnings: list[str] = []
    if delivery.mode == "NO_REPLY" and derived_output:
        warnings.append("NO_REPLY is configured but user-visible content was derived.")
    if delivery.suppressed and stringify(result.get("final_message")):
        warnings.append("A final_message exists but delivery interpretation suppresses it.")
    if result.get("error") or result.get("exception"):
        warnings.append("Result file contains an error or exception field.")
    if not prompt and not payload:
        warnings.append("No prompt or payload was resolved.")
    if "@channel" in derived_output or "@everyone" in derived_output:
        warnings.append("Derived output contains broad notification text.")
    if "webhook" in prompt.lower() or "webhook" in payload.lower():
        warnings.append("Prompt or payload references webhook delivery; replay will not send it.")
    if truthy(job.get("announce")) and delivery.suppressed:
        warnings.append("Job announce flag conflicts with suppressed delivery mode.")
    return warnings


def compare_jobs(before_path: Path, after_path: Path) -> str:
    before = json.dumps(load_json_object(before_path), indent=2, sort_keys=True).splitlines()
    after = json.dumps(load_json_object(after_path), indent=2, sort_keys=True).splitlines()
    return "\n".join(
        unified_diff(
            before,
            after,
            fromfile=str(before_path),
            tofile=str(after_path),
            lineterm="",
        )
    )


def diff_prompt_replay(report: ReplayReport, changed_prompt_path: Path) -> str:
    before = render_terminal(report).splitlines()
    changed = ReplayReport(
        job_id=report.job_id,
        job_name=report.job_name,
        source_files={**report.source_files, "prompt": str(changed_prompt_path)},
        prompt=read_text(changed_prompt_path),
        payload=report.payload,
        derived_output=report.derived_output,
        delivery=report.delivery,
        final_message=report.final_message,
        warnings=report.warnings,
        metadata=report.metadata,
        job=report.job,
    )
    after = render_terminal(changed).splitlines()
    return "\n".join(
        unified_diff(before, after, fromfile="current replay", tofile=str(changed_prompt_path), lineterm="")
    )


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def render_terminal(report: ReplayReport) -> str:
    lines = [
        "OpenClaw Cron Replay",
        f"Job: {report.job_id or '(none)'}{f' ({report.job_name})' if report.job_name else ''}",
    ]
    if report.source_files:
        lines.append("Sources:")
        for name, path in sorted(report.source_files.items()):
            lines.append(f"  {name}: {path}")
    lines.extend(
        [
            "",
            "Resolved prompt/payload:",
            section_value("prompt", report.prompt),
            section_value("payload", report.payload),
            "",
            "Derived user-visible output:",
            indent_block(report.derived_output or "(none)"),
            "",
            "Delivery interpretation:",
        ]
    )
    if report.delivery:
        lines.extend(
            [
                f"  mode: {report.delivery.mode}",
                f"  announced: {str(report.delivery.announced).lower()}",
                f"  suppressed: {str(report.delivery.suppressed).lower()}",
                f"  reason: {report.delivery.reason}",
            ]
        )
    lines.extend(["", "Likely final message text:", indent_block(final_message_display(report))])
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in report.warnings)
    return "\n".join(lines)


def render_markdown(report: ReplayReport) -> str:
    delivery = report.delivery or DeliveryInterpretation("unknown", False, True, "not interpreted")
    warnings = "\n".join(f"- {warning}" for warning in report.warnings) or "- None"
    return "\n".join(
        [
            "# OpenClaw Cron Replay",
            "",
            f"- Job: `{report.job_id or '(none)'}`",
            f"- Name: `{report.job_name or '(none)'}`",
            f"- Delivery mode: `{delivery.mode}`",
            f"- Announced: `{str(delivery.announced).lower()}`",
            f"- Suppressed: `{str(delivery.suppressed).lower()}`",
            f"- Reason: {delivery.reason}",
            "",
            "## Resolved Prompt",
            "",
            fenced(report.prompt or "(none)", "text"),
            "",
            "## Resolved Payload",
            "",
            fenced(report.payload or "(none)", "text"),
            "",
            "## Derived User-Visible Output",
            "",
            fenced(report.derived_output or "(none)", "text"),
            "",
            "## Likely Final Message Text",
            "",
            fenced(final_message_display(report), "text"),
            "",
            "## Warnings",
            "",
            warnings,
        ]
    )


def section_value(name: str, value: str) -> str:
    return f"  {name}:\n{indent_block(value or '(none)', spaces=4)}"


def final_message_display(report: ReplayReport) -> str:
    if report.final_message:
        return report.final_message
    if report.delivery and report.delivery.suppressed:
        return "(suppressed)"
    return "(none)"


def indent_block(value: str, spaces: int = 2) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in value.splitlines())


def fenced(value: str, language: str) -> str:
    return f"```{language}\n{value}\n```"
