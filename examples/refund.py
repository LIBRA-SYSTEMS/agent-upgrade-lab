"""Synthetic refund approval: no real transactions or model calls."""
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command


class State(TypedDict, total=False):
    order: str
    behavior_version: int
    done: bool


def build(version, saver, effects):
    def approve(state):
        amount = 10 if version == "old" or (version == "pinned" and state["behavior_version"] == 1) else 100
        intent = {"operation": "synthetic_refund", "order": state["order"], "amount": amount}
        if interrupt(intent):
            effects.append(intent)
        return {"done": True}
    return StateGraph(State).add_node("approve", approve).add_edge(START, "approve").add_edge("approve", END).compile(checkpointer=saver)


def initial():
    return {"order": "example-only", "behavior_version": 1}


def resume(snapshot):
    return Command(resume=True)


def observe(values, effects):
    return {"done": values.get("done", False), "effects": effects}
