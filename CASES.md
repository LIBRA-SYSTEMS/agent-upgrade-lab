# Versioned case catalog

Executed with LangGraph 1.2.16, checkpoint 4.3.0, SQLite checkpoint 3.1.2 on Python 3.13.14/macOS arm64. These are synthetic inputs, not production incidents or novel vulnerabilities. Re-run on each proposed version; do not assume failures persist forever.

| Case | Input and candidate | Expected observation | Control / provenance |
|---|---|---|---|
| AUL-001 | `refund.py --candidate changed` | Old approval shows 10; candidate emits 100; OBSERVATION_DRIFT | `pinned`: stores business version; documented application compatibility responsibility |
| AUL-002 | `support.py --candidate changed` | Approved internal team becomes synthetic external-vendor destination; OBSERVATION_DRIFT | `pinned`: retains original destination; a second authored application fixture, not an external user's evaluation |
| LG-9001 | `structural.py --candidate remove-key` | Last node remains pending; STILL_PAUSED | `old`: retains key; existing issue #9001 / PR #9108 owns fix |
| LG-8629 | `structural.py --candidate defer` | Resume raises TypeError; RESUME_ERROR | `old`: unchanged defer option; existing issue #8629 / PR #8637 owns fix |

Sources:
- https://docs.langchain.com/oss/python/langgraph/backward-compatibility
- https://github.com/langchain-ai/langgraph/issues/9001
- https://github.com/langchain-ai/langgraph/pull/9108
- https://github.com/langchain-ai/langgraph/issues/8629
- https://github.com/langchain-ai/langgraph/pull/8637

No upstream fix is claimed or submitted here. The useful contribution being evaluated is an attributed, runnable compatibility corpus and consistent evidence, not ownership of those bugs.

## Maintainer error notes

These are defects in this kit, separate from upstream examples. Every accepted fix links to an executable regression, not just a checklist.

| ID | Root cause | Fix and repeatable evidence |
|---|---|---|
| KIT-001 | The report writer accepted the fixture itself or an alias as an output; comparison finished before writing, so fixture preservation was checked too early to cover this write. | Validate the three file identities at the CLI output boundary before execution. `test_report_destinations_cannot_destroy_input_or_each_other` covers direct, symbolic, hard links, companion collision and report-to-report aliasing. |
| KIT-002 | Dynamic fixture import did not register the module before executing dataclass annotations. | Use Python's documented `sys.modules` import lifecycle; `test_dataclass_with_postponed_annotations_loads_as_a_real_module`. |
| KIT-003 | Python equality collapses boolean and number observations. | Compare JSON representations, preserving types; `test_json_boolean_and_number_are_not_equal_business_observations`. |

Workflow for an actual failure: reproduce against the released artifact with synthetic inputs → record the first broken owner → add a regression which fails before the fix → change that owner → rerun the regression and neighboring success cases → verify a clean installed artifact. Do not claim a defect is fixed because its description was added here.
