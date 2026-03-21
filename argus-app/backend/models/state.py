"""In-memory application state singleton.

Thread-safe for single-process FastAPI with uvicorn.
Graph is always MultiDiGraph (Rule 2). Node IDs stored as strings (Rule 8).
"""
import time

import networkx as nx
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppState:
    """Centralized application state. Single instance per process.

    INVARIANTS:
    - graph is ALWAYS MultiDiGraph or None (never DiGraph)
    - ground_truth.crimes[].nodes_involved are ALWAYS string IDs
    - evidence_documents is ALWAYS a list of dicts with "content" key
    - investigations is keyed by case_id (string)
    """
    graph: nx.MultiDiGraph | None = None
    ground_truth: dict = field(default_factory=dict)
    evidence_documents: list[dict[str, Any]] = field(default_factory=list)
    investigations: dict[str, dict[str, Any]] = field(default_factory=dict)
    benchmarks: dict[str, dict[str, Any]] = field(default_factory=dict)
    seed: int = 42
    difficulty: int = 5
    graph_size: int = 5000
    generated_at: str | None = None
    generation_error: str | None = None
    generation_epoch: float = field(default_factory=time.time)


_state = AppState()


def get_state() -> AppState:
    """Return the global AppState singleton."""
    return _state


def reset_state() -> None:
    """Reset all state to defaults. Used by POST /api/reset."""
    global _state
    _state = AppState()
