#!/usr/bin/env python3
"""Run Agent Mini-Suite against a JSON submission."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def nested_get(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def evaluate(value: Any, op: str, expected: Any) -> bool:
    if op == "equals":
        return value == expected
    if op == "in":
        return value in expected
    if op == "contains":
        return expected in (value or [])
    if op == "contains_any":
        return any(item in (value or []) for item in expected)
    if op == "not_contains_any":
        return not any(item in (value or []) for item in expected)
    if op == "regex":
        return re.search(expected, str(value or "")) is not None
    if op == "between":
        return value is not None and expected[0] <= value <= expected[1]
    raise ValueError(f"Unsupported operation: {op}")


def score_task(task: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    checks = []
    raw_score = 0.0
    for criterion in task["criteria"]:
        actual = nested_get(response, criterion["field"])
        # Missing evidence is not evidence of safe or correct behavior.
        passed = actual is not None and evaluate(
            actual, criterion["op"], criterion["value"]
        )
        earned = float(criterion["weight"] if passed else 0)
        raw_score += earned
        checks.append({
            "id": criterion["id"],
            "description": criterion["description"],
            "passed": passed,
            "earned": earned,
            "possible": criterion["weight"],
        })

    cap = float(task["max_score"])
    hard_failures = []
    for rule in task.get("hard_fail", []):
        actual = nested_get(response, rule["field"])
        if evaluate(actual, rule["op"], rule["value"]):
            cap = min(cap, float(rule["cap"]))
            hard_failures.append(rule["reason"])

    return {
        "id": task["id"],
        "title": task["title"],
        "category": task["category"],
        "score": min(raw_score, cap),
        "raw_score": raw_score,
        "max_score": task["max_score"],
        "checks": checks,
        "hard_failures": hard_failures,
    }


def band(score: float) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "capable"
    if score >= 60:
        return "developing"
    return "unreliable"


def run(benchmark: dict[str, Any], submission: dict[str, Any]) -> dict[str, Any]:
    responses = submission.get("responses", {})
    results = [
        score_task(task, responses.get(task["id"], {}))
        for task in benchmark["tasks"]
    ]
    total = sum(item["score"] for item in results)
    maximum = sum(item["max_score"] for item in results)
    normalized = round((total / maximum) * 100, 2) if maximum else 0
    return {
        "benchmark": benchmark["name"],
        "benchmark_version": benchmark["version"],
        "agent": submission.get("agent", "unnamed-agent"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": round(total, 2),
        "max_score": maximum,
        "percentage": normalized,
        "band": band(normalized),
        "tasks": results,
    }


def render_html(report: dict[str, Any]) -> str:
    cards = []
    for task in report["tasks"]:
        checks = "".join(
            '<li class="{kind}">{mark} {label}<span>{earned:g}/{possible:g}</span></li>'.format(
                kind="pass" if check["passed"] else "fail",
                mark="✓" if check["passed"] else "×",
                label=html.escape(check["description"]),
                earned=check["earned"],
                possible=check["possible"],
            )
            for check in task["checks"]
        )
        failures = "".join(
            "<p class='warning'>⚠ {}</p>".format(html.escape(reason))
            for reason in task["hard_failures"]
        )
        cards.append(
            "<section class='card'><div class='card-head'><div><small>{category}</small>"
            "<h2>{title}</h2></div><strong>{score:g}/{maximum:g}</strong></div>"
            "{failures}<ul>{checks}</ul></section>".format(
                category=html.escape(task["category"]),
                title=html.escape(task["title"]),
                score=task["score"],
                maximum=task["max_score"],
                failures=failures,
                checks=checks,
            )
        )

    template = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{benchmark} — {agent}</title>
<style>
:root{{--ink:#172033;--muted:#657086;--paper:#f5f7fb;--card:#fff;--good:#087a55;--bad:#b42335;--accent:#5b45d6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.45 system-ui,sans-serif}}
main{{max-width:900px;margin:auto;padding:48px 20px}}header{{display:grid;grid-template-columns:1fr auto;gap:24px;align-items:end;margin-bottom:28px}}
h1,h2,p{{margin-top:0}}h1{{font-size:clamp(2rem,6vw,4rem);line-height:1}}.score{{font-size:3rem;font-weight:800;color:var(--accent)}}
.card{{background:var(--card);border:1px solid #e1e5ee;border-radius:16px;padding:22px;margin:14px 0;box-shadow:0 6px 18px #2635530a}}
.card-head{{display:flex;justify-content:space-between;gap:16px}}small{{color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}
h2{{font-size:1.2rem;margin:.3rem 0 1rem}}ul{{list-style:none;padding:0;margin:0}}
li{{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-top:1px solid #edf0f5}}
.pass{{color:var(--good)}}.fail,.warning{{color:var(--bad)}}
@media(max-width:560px){{header{{grid-template-columns:1fr}}.score{{font-size:2.4rem}}}}
</style></head><body><main><header><div><small>{benchmark}</small><h1>{agent}</h1>
<p>{band} performance</p></div><div class="score">{score:g}/{maximum:g}</div></header>
{cards}</main></body></html>"""
    return template.format(
        benchmark=html.escape(report["benchmark"]),
        agent=html.escape(report["agent"]),
        band=report["band"].title(),
        score=report["score"],
        maximum=report["max_score"],
        cards="".join(cards),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", type=Path)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path(__file__).with_name("benchmark.json"),
    )
    parser.add_argument("--output", type=Path, default=Path("results/latest"))
    args = parser.parse_args()
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    submission = json.loads(args.submission.read_text(encoding="utf-8"))
    report = run(benchmark, submission)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "report.html").write_text(render_html(report), encoding="utf-8")
    print(
        f"{report['agent']}: {report['score']:g}/{report['max_score']:g} "
        f"({report['band']})"
    )


if __name__ == "__main__":
    main()
