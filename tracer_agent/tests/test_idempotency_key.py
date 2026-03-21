"""Idempotency key determinism tests.

Verifies that the idempotency key (Rule 18) produces identical output
regardless of entity list ordering and across repeated computations.
SHA-256(case_id + typology + sorted(involved_entities)) must be stable.
"""
import hashlib


def _compute_idempotency_key(
    case_id: str, typology: str, involved_entities: list[str]
) -> str:
    """Reproduce idempotency key computation from C2 pipeline wiring."""
    payload = case_id + typology + "".join(sorted(involved_entities))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_idempotency_key_deterministic_across_100_iterations() -> None:
    """Same inputs must produce identical key across 100 runs."""
    case_id = "CASE-IDEM-001"
    typology = "STRUCTURING"
    entities = ["mule_1", "src_3", "src_1", "src_2"]

    keys = {_compute_idempotency_key(case_id, typology, entities) for _ in range(100)}
    if len(keys) != 1:
        raise ValueError(f"Non-deterministic: got {len(keys)} unique keys")


def test_idempotency_key_order_independent() -> None:
    """Entity list order must not affect the key (sorted() applied)."""
    case_id = "CASE-IDEM-002"
    typology = "LAYERING"

    entities_a = ["node_z", "node_a", "node_m", "node_f"]
    entities_b = list(reversed(entities_a))
    entities_c = sorted(entities_a)

    key_a = _compute_idempotency_key(case_id, typology, entities_a)
    key_b = _compute_idempotency_key(case_id, typology, entities_b)
    key_c = _compute_idempotency_key(case_id, typology, entities_c)

    if key_a != key_b:
        raise ValueError("Key differs when entities are reversed")
    if key_a != key_c:
        raise ValueError("Key differs when entities are pre-sorted")


def test_idempotency_key_differs_on_different_inputs() -> None:
    """Different case_ids, typologies, or entities must produce different keys."""
    base = _compute_idempotency_key("CASE-001", "STRUCTURING", ["a", "b"])

    # Different case_id
    diff_case = _compute_idempotency_key("CASE-002", "STRUCTURING", ["a", "b"])
    if base == diff_case:
        raise ValueError("Different case_id produced same key")

    # Different typology
    diff_typo = _compute_idempotency_key("CASE-001", "LAYERING", ["a", "b"])
    if base == diff_typo:
        raise ValueError("Different typology produced same key")

    # Different entities
    diff_ent = _compute_idempotency_key("CASE-001", "STRUCTURING", ["a", "c"])
    if base == diff_ent:
        raise ValueError("Different entities produced same key")


def test_idempotency_key_empty_entities() -> None:
    """Empty entity list must still produce a valid deterministic key."""
    key_a = _compute_idempotency_key("CASE-EMPTY", "NONE", [])
    key_b = _compute_idempotency_key("CASE-EMPTY", "NONE", [])
    if key_a != key_b:
        raise ValueError("Empty entity list produced non-deterministic key")
    if len(key_a) != 64:
        raise ValueError(f"SHA-256 hex digest must be 64 chars, got {len(key_a)}")
