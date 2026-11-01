"""A second application: approval of an escalation destination."""
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command


class State(TypedDict, total=False):
    ticket: str
    approved_team: str
    destination: str


def build(version, saver, effects):
    def dispatch(state):
        destination = state["approved_team"] if version in {"old", "pinned"} else "external-vendor"
        approved = interrupt({"ticket": state["ticket"], "destination": destination})
        if approved:
            effects.append({"operation": "synthetic_route", "ticket": state["ticket"], "destination": destination})
        return {"destination": destination}
    return StateGraph(State).add_node("dispatch", dispatch).add_edge(START, "dispatch").add_edge("dispatch", END).compile(checkpointer=saver)


def initial():
    return {"ticket": "synthetic-T1", "approved_team": "internal-support"}


def resume(snapshot):
    return Command(resume=True)


def observe(values, effects):
    return {"destination": values.get("destination"), "effects": effects}
