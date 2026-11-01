"""One process and one SQLite connection per preparation or resume."""
import argparse
import contextlib
import importlib.util
import json
import os
import sys
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def load_fixture(path):
    sys.path.insert(0, str(Path(path).resolve().parent))
    spec = importlib.util.spec_from_file_location("upgrade_fixture", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def execute(path, version, phase, db):
    effects = []
    result = {"pid": os.getpid(), "phase": phase, "version": version}
    # Fixture diagnostics must not corrupt the machine-readable result on stdout.
    with contextlib.redirect_stdout(sys.stderr):
        try:
            fixture = load_fixture(path)
            with SqliteSaver.from_conn_string(db) as saver:
                graph = fixture.build(version, saver, effects)
                config = {"configurable": {"thread_id": "upgrade-rehearsal"}}
                value = fixture.initial() if phase == "prepare" else fixture.resume(graph.get_state(config))
                graph.invoke(value, config)
                state = graph.get_state(config)
                result.update(status="returned", next=list(state.next), interrupts=[i.value for i in state.interrupts])
                if phase == "resume":
                    result["observation"] = fixture.observe(state.values, effects)
                # Detect an unusable fixture result while the boundary is still attributable.
                json.dumps(result, allow_nan=False)
        except Exception as exc:
            result = {"pid": os.getpid(), "phase": phase, "version": version,
                      "status": "error", "error_type": type(exc).__name__, "error": str(exc)}
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fixture")
    p.add_argument("version")
    p.add_argument("phase", choices=["prepare", "resume"])
    p.add_argument("db")
    a = p.parse_args()
    print(json.dumps(execute(a.fixture, a.version, a.phase, a.db), allow_nan=False))


if __name__ == "__main__":
    main()
