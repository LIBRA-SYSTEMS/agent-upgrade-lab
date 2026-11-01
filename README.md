# Agent Upgrade Lab — development preview

A small, versioned regression case kit for paused-agent upgrades, with a reusable local runner. Rehearse paused LangGraph workflows against candidate application code. A fresh-run test can pass while an older approval resumes with changed behavior. This tool makes that difference reproducible with one checkpoint, separate processes, and a shareable report.

This is an early development preview (0.1.0.dev1), not a stable release. It is not a migration engine, sandbox, security scanner, or approval service. It does not fix LangGraph. Run only trusted synthetic fixtures with external tools replaced by in-memory observations.

## Run locally

Requires Python 3.11 or newer; verified with installed wheels on Python 3.11.15, 3.12.11 and 3.13.14/macOS arm64, with langgraph 1.2.16 (the lock file) and again on 2026-11-01 with langgraph 1.2.19, langgraph-checkpoint 4.3.1 and langgraph-checkpoint-sqlite 3.1.3 (31 tests passed on both). Windows, Linux and newer Python versions have not been verified.

```sh
python -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/agent-upgrade examples/refund.py --candidate changed --output result.json
# Exit 1: OBSERVATION_DRIFT (shown approval 10, resumed synthetic effect 100)
.venv/bin/agent-upgrade examples/refund.py --candidate pinned --output pinned.json
# Exit 0: MATCH
.venv/bin/agent-upgrade examples/support.py --candidate changed --output support.json
# Exit 1: internal support becomes an external-vendor synthetic destination
```

JSON and a companion `<output>.md` report show preparation, baseline resume, candidate resume, versions, exact observations, and checkpoint preservation. Exit 0 means MATCH for the provided observation; 1 means candidate drift/failure; 2 means the reference or comparison was not valid. A failure to reach a real pause never passes.

The fixture and the two report paths must refer to different files, including symlinks and hardlinks. The CLI rejects a collision before running the fixture; report writing cannot intentionally target its input. Existing report files at distinct paths are overwritten when explicitly selected. Keep imported helper sources separate from report paths.

## Bring a fixture

A trusted Python file implements four small functions. The example files are complete applications:

- `build(version, saver, effects)` returns a compiled LangGraph graph using the supplied SQLite saver. Select application code by `version`.
- `initial()` returns a fresh synthetic input dictionary.
- `resume(snapshot)` returns a public LangGraph resume input, such as `Command(resume=True)` or `None` for a static breakpoint.
- `observe(values, effects)` returns the JSON-serializable business outcome to compare. Include every outcome that matters; an incomplete observation can miss a regression.

The worker prepares with `--baseline` (default `old`), closes the SQLite connection, then resumes separate copies with baseline and candidate code. Both use the same installed dependencies. Separate dependency environments, production DB import, concurrent changes, PostgreSQL, multiple approval rounds, and Windows are not verified. Checkpoint migration is not performed.

Fixture code executes with your Python user's permissions. It must not call production tools, spawn child process trees, or use real customer checkpoints. Tracing is disabled for the bundled workers; this does not prevent arbitrary fixture network calls. Timeout applies to each direct worker, not arbitrary descendants.

## Why not just pytest?

You can write the same experiment directly in pytest, and for one application that may be simpler. The intended benefit is reusing the process/checkpoint/report lifecycle across fixtures. This preview must earn its place through actual users; it has no demonstrated adoption or measured human time savings. See `tests/test_baseline.py` for a standalone three-process comparison of the same business failure without importing this package.

## Attribution

The approval examples illustrate documented application compatibility responsibility, not a new SDK vulnerability. Structural examples reproduce existing issues #9001 (removed state key) and #8629 (defer option). Both issues are still open as of 2026-11-01; the earlier fix PRs #9108 and #8637 were closed without merging.

- https://docs.langchain.com/oss/python/langgraph/backward-compatibility
- https://github.com/langchain-ai/langgraph/issues/9001
- https://github.com/langchain-ai/langgraph/issues/8629

Research considered official saver conformance, AgentCI, langgraph-replay, and graph migration tools. This prototype does not claim global novelty. Public repository ownership, release name/license, and external outreach remain separate release decisions.

## Short demo and tests

```sh
.venv/bin/python demo.py --output demo-results
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest tests -q
```

The demo prints a changed refund, the documented behavior-version control, and a changed support destination. Expected failing candidates exit 1; the demo itself exits 0 only when those differences are reproduced. The test suite also demonstrates an intentional blind spot: omitting the effect from `observe` makes a changed action invisible. MATCH is never a business-safety certificate.

`requirements-lock.txt` records the exact verification environment; the project metadata pins runtime dependencies. No automatic GitHub Actions or paid services are configured.

## What this project contributes today

The current deliverable is a reproducible case kit, not a proven new enterprise product. `CASES.md` separates documented application behavior from attributed upstream defects. A standalone pytest comparison catches the same failures under the same process/checkpoint conditions. The reusable runner adds consistent reports and avoids recopying that lifecycle into each new case; it has not demonstrated unique detection, user adoption, or human time savings.

The report hashes the fixture file and rejects changes during the run. That hash does not freeze arbitrary imported helper files or certify the whole environment. The checked-in dependency lock and package manifest describe the tested snapshot.

## License

MIT, see [LICENSE](LICENSE).
