"""Compare two application versions using copies of one paused checkpoint."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def worker(fixture, version, phase, db, timeout):
    env = dict(os.environ, LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
    try:
        process = subprocess.run([sys.executable, "-m", "agent_upgrade_lab.worker", str(fixture), version, phase, str(db)],
                                 capture_output=True, text=True, timeout=timeout, env=env)
        if process.returncode:
            return {"status": "harness_error", "error": process.stderr, "returncode": process.returncode}
        value = json.loads(process.stdout)
        value["diagnostics"] = process.stderr
        return value
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return {"status": "harness_error", "error_type": type(exc).__name__, "error": str(exc)}


def compare(fixture, baseline="old", candidate="changed", timeout=20):
    fixture = Path(fixture).resolve()
    started = time.monotonic()
    fixture_hash = sha256(fixture) if fixture.is_file() else None
    result = {"format_version": 1, "fixture": fixture.name, "fixture_sha256": fixture_hash, "baseline_version": baseline,
              "candidate_version": candidate, "python": sys.version, "platform": platform.platform(), "packages": {name: importlib.metadata.version(name) for name in
              ["agent-upgrade-lab", "langgraph", "langgraph-checkpoint", "langgraph-checkpoint-sqlite"]}}
    with tempfile.TemporaryDirectory(prefix="agent-upgrade-") as temp:
        root = Path(temp)
        original = root / "paused.sqlite"
        prepared = worker(fixture, baseline, "prepare", original, timeout)
        result["prepare"] = prepared
        if prepared["status"] != "returned":
            result.update(verdict="REFERENCE_ERROR", exit_code=2)
        elif not prepared["next"]:
            result.update(verdict="NO_PAUSE", exit_code=2)
        else:
            original_hash = sha256(original)
            for label, version in [("baseline", baseline), ("candidate", candidate)]:
                db = root / f"{label}.sqlite"
                shutil.copyfile(original, db)
                result[label] = worker(fixture, version, "resume", db, timeout)
            result["source_preserved"] = sha256(original) == original_hash
            result["checkpoint_sha256"] = original_hash
            before, after = result["baseline"], result["candidate"]
            if not result["source_preserved"] or any(v["status"] == "harness_error" for v in [before, after]):
                result.update(verdict="HARNESS_ERROR", exit_code=2)
            elif before["status"] != "returned" or before["next"]:
                result.update(verdict="REFERENCE_INCOMPLETE", exit_code=2)
            elif after["status"] != "returned":
                result.update(verdict="RESUME_ERROR", exit_code=1)
            elif after["next"]:
                result.update(verdict="STILL_PAUSED", exit_code=1)
            elif json.dumps(before["observation"], sort_keys=True) != json.dumps(after["observation"], sort_keys=True):
                result.update(verdict="OBSERVATION_DRIFT", exit_code=1)
            else:
                result.update(verdict="MATCH", exit_code=0)
    result["fixture_preserved"] = fixture.is_file() and sha256(fixture) == fixture_hash
    if fixture_hash is not None and not result["fixture_preserved"]:
        result.update(verdict="HARNESS_ERROR", exit_code=2)
    result["temporary_data_removed"] = not root.exists()
    result["elapsed_seconds"] = round(time.monotonic() - started, 4)
    return result


def markdown(result):
    lines = [f"# Upgrade rehearsal: {result['verdict']}", "",
             f"Fixture: `{result['fixture']}`; `{result['baseline_version']}` → `{result['candidate_version']}`.", "",
             "This compares the fixture's observation, not all business behavior or security properties.", ""]
    for label in ["prepare", "baseline", "candidate"]:
        if label in result:
            lines += [f"## {label}", "", "```json", json.dumps(result[label], ensure_ascii=False, indent=2), "```", ""]
    lines += [f"Original checkpoint preserved: {result.get('source_preserved', 'not reached')}",
              f"Temporary data removed: {result['temporary_data_removed']}"]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description="Rehearse trusted synthetic LangGraph fixtures across application code changes.")
    p.add_argument("fixture", type=Path)
    p.add_argument("--baseline", default="old")
    p.add_argument("--candidate", default="changed")
    p.add_argument("--timeout", type=float, default=20, help="seconds per worker (default: 20)")
    p.add_argument("--output", type=Path, help="write JSON and a companion .md report")
    a = p.parse_args()
    if a.timeout <= 0:
        p.error("--timeout must be positive")
    if a.output:
        destinations = [a.output, a.output.with_name(a.output.name + ".md")]
        paths = [a.fixture, *destinations]
        for index, path in enumerate(paths):
            for other in paths[index + 1:]:
                if path.resolve() == other.resolve() or (path.exists() and other.exists() and path.samefile(other)):
                    p.error("fixture and both report destinations must be different files")
    result = compare(a.fixture, a.baseline, a.candidate, a.timeout)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(rendered, encoding="utf-8")
        destinations[1].write_text(markdown(result), encoding="utf-8")
    print(rendered, end="")
    return result["exit_code"]
