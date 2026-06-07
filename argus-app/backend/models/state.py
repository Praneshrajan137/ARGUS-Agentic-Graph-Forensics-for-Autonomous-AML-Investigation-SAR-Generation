"""In-memory application state singleton.

Thread-safe for single-process FastAPI with uvicorn.
Graph is always MultiDiGraph (Rule 2). Node IDs stored as strings (Rule 8).

v9.0: Explicit thread safety via RLock around mutable collections.
"""
import threading
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

    THREAD SAFETY:
    - All mutations to `investigations` and `benchmarks` MUST hold `_lock`.
    - Read-only access to `graph` after startup is safe without the lock
      (graph is write-once during lifespan startup, never mutated after).
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

    # Explicit RLock for thread-safe mutation of investigations/benchmarks.
    # RLock (reentrant) allows the same thread to acquire multiple times
    # without deadlocking — needed because _update_step is called from
    # within run_investigation which already holds context.
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


_state = AppState()


def get_state() -> AppState:
    """Return the global AppState singleton."""
    return _state


def reset_state() -> None:
    """Reset all state to defaults. Used by POST /api/reset."""
    global _state
    _state = AppState()
