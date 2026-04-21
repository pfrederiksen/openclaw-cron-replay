from __future__ import annotations

import json
from pathlib import Path

from openclaw_cron_replay.cli import main
from openclaw_cron_replay.core import replay


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_replaying_result_file_driven_job() -> None:
    report = replay(
        job_id="news-digest",
        jobs_path=FIXTURES / "jobs.json",
        result_path=FIXTURES / "results" / "news_digest_result.json",
    )

    assert report.derived_output.startswith("Today in OpenClaw")
    assert report.delivery is not None
    assert report.delivery.mode == "announce"
    assert report.final_message == report.derived_output


def test_replaying_text_return_announce_job() -> None:
    report = replay(
        job_id="text-return-announcer",
        jobs_path=FIXTURES / "jobs.json",
        result_path=FIXTURES / "results" / "text_return_result.json",
    )

    assert "Deploy window is clear" in report.derived_output
    assert report.delivery is not None
    assert report.delivery.mode == "text-return"
    assert report.delivery.announced is True


def test_no_reply_suppression_logic() -> None:
    report = replay(
        job_id="no-reply-job",
        jobs_path=FIXTURES / "jobs.json",
        result_path=FIXTURES / "results" / "no_reply_with_content.json",
    )

    assert report.delivery is not None
    assert report.delivery.suppressed is True
    assert report.final_message == ""
    assert "NO_REPLY is configured but user-visible content was derived." in report.warnings


def test_delivery_interpretation_silent_job() -> None:
    report = replay(
        job_id="silent-health-check",
        jobs_path=FIXTURES / "jobs.json",
        result_path=FIXTURES / "results" / "silent_result.json",
    )

    assert report.delivery is not None
    assert report.delivery.mode == "silent"
    assert report.delivery.announced is False
    assert report.delivery.suppressed is True


def test_cli_json_output(capsys) -> None:
    exit_code = main(
        [
            "--job",
            "news-digest",
            "--jobs",
            str(FIXTURES / "jobs.json"),
            "--result",
            str(FIXTURES / "results" / "news_digest_result.json"),
            "--json",
        ]
    )

    assert exit_code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["job_id"] == "news-digest"
    assert data["delivery"]["mode"] == "announce"
