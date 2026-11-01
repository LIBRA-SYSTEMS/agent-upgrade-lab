"""Standalone cheapest alternative. No import from agent_upgrade_lab.

Same synthetic fixture, same disk checkpoint copies, three separate processes.
Handwritten pytest detects the same business drift without the package.
"""
import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

WORKER = '''
import contextlib,json,runpy,sys
from langgraph.checkpoint.sqlite import SqliteSaver
with contextlib.redirect_stdout(sys.stderr):
    fixture=runpy.run_path(sys.argv[1]); effects=[]
    with SqliteSaver.from_conn_string(sys.argv[2]) as saver:
        graph=fixture['build'](sys.argv[3],saver,effects)
        config={'configurable':{'thread_id':'baseline'}}
        arg=fixture['initial']() if sys.argv[4]=='prepare' else fixture['resume'](graph.get_state(config))
        graph.invoke(arg,config); state=graph.get_state(config)
        observed=None if sys.argv[4]=='prepare' else fixture['observe'](state.values,effects)
print(json.dumps({'next':list(state.next),'observed':observed}))
'''


def execute(fixture, db, version, phase):
    env = dict(os.environ, LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
    p = subprocess.run([sys.executable, "-c", WORKER, str(fixture), str(db), version, phase],
                       text=True, capture_output=True, check=True, timeout=20, env=env)
    return json.loads(p.stdout)


@pytest.mark.parametrize("name", ["refund.py", "support.py"])
@pytest.mark.parametrize("candidate,changed", [("changed", True), ("pinned", False)])
def test_standalone_pytest_detects_same_problem(name, candidate, changed):
    fixture = Path(__file__).resolve().parents[1] / "examples" / name
    with tempfile.TemporaryDirectory(prefix="upgrade-baseline-") as folder:
        root = Path(folder)
        original = root / "original.sqlite"
        prepared = execute(fixture, original, "old", "prepare")
        assert prepared["next"]
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        old, new = root / "old.sqlite", root / "new.sqlite"
        shutil.copyfile(original, old); shutil.copyfile(original, new)
        baseline = execute(fixture, old, "old", "resume")
        after = execute(fixture, new, candidate, "resume")
        assert not baseline["next"] and not after["next"]
        assert (baseline["observed"] != after["observed"]) is changed
        assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
