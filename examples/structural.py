"""Attributed reproductions of LangGraph #9001 and #8629, not new discoveries."""
import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END


class Old(TypedDict, total=False):
    log: Annotated[list[str], operator.add]
    note: str


class New(TypedDict, total=False):
    log: Annotated[list[str], operator.add]


def build(version, saver, effects):
    schema = New if version == "remove-key" else Old
    def first(_):
        return {"log": ["first"], **({"note": "x"} if schema is Old else {})}
    def last(_):
        effects.append({"operation": "synthetic_last"})
        return {"log": ["last"]}
    return (StateGraph(schema).add_node("first", first).add_node("last", last, defer=version == "defer")
            .add_edge(START, "first").add_edge("first", "last").add_edge("last", END)
            .compile(checkpointer=saver, interrupt_before=["last"]))


def initial():
    return {"log": []}


def resume(snapshot):
    return None


def observe(values, effects):
    return {"log": values.get("log"), "effects": effects}
