# Agent Mini-Suite

A compact, offline benchmark for five practical agent capabilities:

1. ambiguity handling;
2. real-work execution;
3. memory and continuity;
4. safety under prompt injection;
5. verification and honest reporting.

The benchmark accepts a JSON submission, applies transparent deterministic
checks, and writes JSON plus a standalone HTML report. It needs no API key or
third-party package.

## Quick start

```bash
python run_benchmark.py examples/strong_agent.json --output results/strong
python run_benchmark.py examples/weak_agent.json --output results/weak
python -m unittest discover -s tests -v
```

Open `results/strong/report.html` to inspect the result.

## Scoring

Each task is worth 20 points. Explicit weighted requirements use exact values,
membership checks, and regular expressions. Hard-fail rules cap scores after
critical safety or honesty violations.

- 90–100: excellent
- 75–89: capable
- 60–74: developing
- below 60: unreliable

The suite evaluates observable decisions, not hidden chain-of-thought. It is a
portable seed benchmark rather than a claim to measure general intelligence.
For a larger competition, pair these checks with blinded human review or a
calibrated judge model.
