import json
from pathlib import Path
import subprocess
import sys

import pytest
from agent_upgrade_lab.cli import compare

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("fixture,candidate,verdict,code", [
    ("refund.py", "old", "MATCH", 0),
    ("refund.py", "changed", "OBSERVATION_DRIFT", 1),
    ("refund.py", "pinned", "MATCH", 0),
    ("support.py", "old", "MATCH", 0),
    ("support.py", "changed", "OBSERVATION_DRIFT", 1),
    ("support.py", "pinned", "MATCH", 0),
    ("structural.py", "old", "MATCH", 0),
    ("structural.py", "remove-key", "STILL_PAUSED", 1),
    ("structural.py", "defer", "RESUME_ERROR", 1),
])
def test_actual_checkpoint_and_worker_matrix(fixture, candidate, verdict, code):
    result = compare(ROOT / "examples" / fixture, candidate=candidate)
    assert (result["verdict"], result["exit_code"]) == (verdict, code)
    assert result["source_preserved"] and result["temporary_data_removed"]
    assert len({result[key]["pid"] for key in ["prepare", "baseline", "candidate"]}) == 3
    if candidate == "changed":
        assert result["baseline"]["observation"] != result["candidate"]["observation"]
    if candidate == "defer":
        assert result["candidate"]["error_type"] == "TypeError"


def fixture_at(tmp_path, source):
    target = tmp_path / "fixture.py"
    target.write_text(source)
    return target


def test_completed_reference_is_not_a_valid_pause(tmp_path):
    fixture = fixture_at(tmp_path, '''
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
class State(TypedDict):
    count: int
def build(version,saver,effects):
    return StateGraph(State).add_node('work',lambda s: {'count':1}).add_edge(START,'work').add_edge('work',END).compile(checkpointer=saver)
def initial():return {'count':0}
''')
    result = compare(fixture)
    assert result["verdict"] == "NO_PAUSE" and result["exit_code"] == 2
    assert result["temporary_data_removed"]


def test_failed_reference_cannot_pass(tmp_path):
    source = (ROOT / "examples/refund.py").read_text().replace('return Command(resume=True)', 'raise RuntimeError("reference resume failed")')
    result = compare(fixture_at(tmp_path, source))
    assert result["verdict"] == "REFERENCE_INCOMPLETE" and result["exit_code"] == 2


def test_timeout_reports_invalid_comparison(tmp_path):
    fixture = fixture_at(tmp_path, 'import time\ntime.sleep(5)\n')
    result = compare(fixture, timeout=0.05)
    assert result["verdict"] == "REFERENCE_ERROR" and result["exit_code"] == 2
    assert result["prepare"]["error_type"] == "TimeoutExpired"
    assert result["temporary_data_removed"]


def test_fixture_output_does_not_corrupt_protocol(tmp_path):
    source = (ROOT / "examples/refund.py").read_text() + '\nprint("fixture diagnostic")\n'
    result = compare(fixture_at(tmp_path, source), candidate="pinned")
    assert result["verdict"] == "MATCH"
    assert "fixture diagnostic" in result["candidate"]["diagnostics"]


def test_observation_cannot_be_nonfinite_json(tmp_path):
    source = (ROOT / "examples/refund.py").read_text().replace('return {"done": values.get("done", False), "effects": effects}', 'return {"amount": float("nan")}')
    result = compare(fixture_at(tmp_path, source))
    assert result["exit_code"] == 2


def test_cli_nonzero_and_distinct_report_files(tmp_path):
    out = tmp_path / "custom.md"
    exe = Path(sys.executable).parent / "agent-upgrade"
    p = subprocess.run([str(exe), str(ROOT / "examples/support.py"), "--output", str(out)], capture_output=True, text=True)
    assert p.returncode == 1
    assert json.loads(out.read_text())["verdict"] == "OBSERVATION_DRIFT"
    assert "OBSERVATION_DRIFT" in Path(str(out) + ".md").read_text()


def test_declared_observation_is_the_detection_boundary(tmp_path):
    # Negative capability demonstration: no tool can infer omitted business intent.
    source = (ROOT / "examples/refund.py").read_text().replace('return {"done": values.get("done", False), "effects": effects}', 'return {"done": values.get("done", False)}')
    result = compare(fixture_at(tmp_path, source))
    assert result["verdict"] == "MATCH"  # documented blind spot; not a safety certification


def test_json_boolean_and_number_are_not_equal_business_observations(tmp_path):
    source = (ROOT / "examples/refund.py").read_text().replace('return {"done": values.get("done", False), "effects": effects}', 'return {"value": True if effects[0]["amount"] == 10 else 1}')
    result = compare(fixture_at(tmp_path, source))
    assert result["verdict"] == "OBSERVATION_DRIFT"


def test_missing_effect_is_a_regression(tmp_path):
    source = (ROOT / "examples/refund.py").read_text().replace('if interrupt(intent):', 'if interrupt(intent) and version != "dropped":')
    result = compare(fixture_at(tmp_path, source), candidate="dropped")
    assert result["verdict"] == "OBSERVATION_DRIFT"
    assert result["candidate"]["observation"]["effects"] == []


@pytest.mark.parametrize("candidate", ["pinned", "changed"])
def test_fixture_changed_during_run_cannot_pass(tmp_path, candidate):
    source = (ROOT / "examples/refund.py").read_text().replace('def initial():', 'def initial():\n    from pathlib import Path\n    p=Path(__file__); p.write_text(p.read_text()+"\\n# changed during run\\n")')
    result = compare(fixture_at(tmp_path, source), candidate=candidate)
    assert not result["fixture_preserved"]
    assert result["verdict"] == "HARNESS_ERROR" and result["exit_code"] == 2


def test_dataclass_with_postponed_annotations_loads_as_a_real_module(tmp_path):
    fixture = fixture_at(tmp_path, '''
from __future__ import annotations
from dataclasses import dataclass
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
@dataclass
class State:
    value: int = 10
def build(version, saver, effects):
    def work(state):
        if interrupt({'value':state.value}):effects.append({'value':state.value})
        return {'value':state.value}
    return StateGraph(State).add_node('work',work).add_edge(START,'work').add_edge('work',END).compile(checkpointer=saver)
def initial():return {'value':10}
def resume(snapshot):return Command(resume=True)
def observe(values,effects):return {'effects':effects}
''')
    result = compare(fixture, candidate="old")
    assert result["verdict"] == "MATCH" and result["exit_code"] == 0
    assert result["candidate"]["observation"] == {"effects": [{"value": 10}]}


@pytest.mark.parametrize('mode', ['direct', 'symlink', 'hardlink', 'companion', 'reports-symlink', 'reports-hardlink'])
def test_report_destinations_cannot_destroy_input_or_each_other(tmp_path, mode):
    source = (ROOT / 'examples/refund.py').read_bytes()
    fixture = tmp_path / 'fixture.py'
    fixture.write_bytes(source)
    output = tmp_path / 'result.json'
    companion = Path(str(output) + '.md')
    if mode == 'direct':
        output = fixture
    elif mode == 'symlink':
        output.symlink_to(fixture)
    elif mode == 'hardlink':
        output.hardlink_to(fixture)
    elif mode == 'companion':
        companion.symlink_to(fixture)
    else:
        output.write_text('original report', encoding='utf-8')
        if mode == 'reports-symlink':
            companion.symlink_to(output)
        else:
            companion.hardlink_to(output)
    exe = Path(sys.executable).parent / 'agent-upgrade'
    p = subprocess.run([str(exe), str(fixture), '--candidate', 'old', '--output', str(output)], capture_output=True, text=True, timeout=30)
    assert p.returncode == 2
    assert fixture.read_bytes() == source
    if mode.startswith('reports-'):
        assert output.read_text(encoding='utf-8') == 'original report'
    assert 'different files' in p.stderr
