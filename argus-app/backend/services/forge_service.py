"""FORGE service — wraps the synthetic financial crime data generator.

All graph operations produce MultiDiGraph (Rule 2).
All monetary values use Decimal(str()) (Rule 1).
All node IDs stored as strings in ground_truth (Rule 8).
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import networkx as nx

from src.core.graph_generator import (
    generate_scale_free_graph,
    add_entity_attributes,
    add_transaction_attributes,
)
from src.core.crime_injector import (
    inject_structuring,
    inject_layering,
    StructuringConfig,
    LayeringConfig,
)
from ..models.state import get_state

logger = logging.getLogger(__name__)


def generate_world(
    seed: int = 42,
    difficulty: int = 5,
    node_count: int = 1000,
) -> None:
    """Generate a complete synthetic financial world with injected crimes.

    Pipeline: scale-free graph → entity attrs → transaction attrs →
              inject structuring → inject layering → collect evidence

    Follows main.py path (MultiDiGraph throughout). D-49: init_server.py
    DiGraph conversion is a LEGACY path not used by the unified backend.
    """
    state = get_state()

    # Step 1: Generate base graph
    # nx.scale_free_graph returns MultiDiGraph natively
    G = generate_scale_free_graph(n_nodes=node_count, seed=seed)

    # Defensive MultiDiGraph enforcement (D-49)
    if not isinstance(G, nx.MultiDiGraph):
        logger.warning("Graph was %s, converting to MultiDiGraph", type(G).__name__)
        G = nx.MultiDiGraph(G)

    G = add_entity_attributes(G, seed=seed)
    G = add_transaction_attributes(G, seed=seed)

    # Step 2: Inject structuring (fan-in: 20 smurfs → 1 mule)
    mule_id = list(G.nodes())[0]
    struct_config = StructuringConfig(mule_node=mule_id, difficulty=difficulty)
    G, struct_crime = inject_structuring(
        G, config=struct_config, seed=seed, generate_evidence=True
    )

    # Step 3: Inject layering (decay chain: 5 hops)
    source = list(G.nodes())[10]
    dest = list(G.nodes())[20]
    layer_config = LayeringConfig(chain_length=5, difficulty=difficulty)
    G, layer_crime = inject_layering(
        G, config=layer_config,
        source_node=source, dest_node=dest,
        seed=seed + 1, generate_evidence=True,
    )

    # Defensive MultiDiGraph re-check after injection
    if not isinstance(G, nx.MultiDiGraph):
        logger.warning("Post-injection graph was %s, re-converting", type(G).__name__)
        G = nx.MultiDiGraph(G)

    # Step 4: Collect evidence artifacts
    all_evidence = (
        struct_crime.metadata.get("evidence_artifacts", [])
        + layer_crime.metadata.get("evidence_artifacts", [])
    )

    # Step 5: Build ground truth with STRING node IDs (Rule 8)
    ground_truth = {
        "crimes": [
            {
                "crime_type": "structuring",
                "nodes_involved": sorted(str(n) for n in struct_crime.nodes_involved),
                "edges_involved": sorted(
                    (str(u), str(v)) for u, v in struct_crime.edges_involved
                ),
                "metadata": {
                    k: v
                    for k, v in struct_crime.metadata.items()
                    if k != "evidence_artifacts"
                },
            },
            {
                "crime_type": "layering",
                "nodes_involved": sorted(str(n) for n in layer_crime.nodes_involved),
                "edges_involved": sorted(
                    (str(u), str(v)) for u, v in layer_crime.edges_involved
                ),
                "metadata": {
                    k: v
                    for k, v in layer_crime.metadata.items()
                    if k != "evidence_artifacts"
                },
            },
        ],
        "difficulty": difficulty,
    }

    # Step 6: Persist to AppState
    state.graph = G
    state.ground_truth = ground_truth
    state.evidence_documents = all_evidence
    state.seed = seed
    state.difficulty = difficulty
    state.graph_size = node_count
    state.generated_at = datetime.now().isoformat()
    state.generation_error = None

    logger.info(
        "World generated: %d nodes, %d edges, %d evidence docs",
        G.number_of_nodes(), G.number_of_edges(), len(all_evidence),
    )


def get_graph_stats() -> dict[str, Any]:
    """Return graph statistics and crime summary."""
    state = get_state()
    if state.graph is None:
        return {"node_count": 0, "edge_count": 0, "density": 0.0, "avg_degree": 0.0,
                "crime_summary": [], "seed": state.seed, "difficulty": state.difficulty,
                "generated_at": state.generated_at}

    G = state.graph
    n = G.number_of_nodes()
    e = G.number_of_edges()

    crime_summary = []
    for crime in state.ground_truth.get("crimes", []):
        crime_summary.append({
            "crime_type": crime["crime_type"],
            "node_count": len(crime["nodes_involved"]),
            "edge_count": len(crime["edges_involved"]),
            "metadata": {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in crime.get("metadata", {}).items()
                if k in ("mule_id", "total_amount", "source_node", "dest_node", "chain_length")
            },
        })

    return {
        "node_count": n,
        "edge_count": e,
        "density": nx.density(G) if n > 0 else 0.0,
        "avg_degree": (2.0 * e / n) if n > 0 else 0.0,
        "crime_summary": crime_summary,
        "seed": state.seed,
        "difficulty": state.difficulty,
        "generated_at": state.generated_at,
    }


def get_visualization_data(limit: int = 500) -> dict[str, Any]:
    """Return nodes and edges for D3 force-directed graph.

    Node classification reads ALL crimes from ground_truth (not by index).
    Group values: "legitimate", "structuring_source", "structuring_mule", "layering"
    Edge labels come from actual edge attribute ("legitimate"/"structuring"/"layering").
    """
    state = get_state()
    if state.graph is None:
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}

    G = state.graph
    ground_truth = state.ground_truth

    # Build classification sets from ALL crimes
    structuring_sources: set[str] = set()
    mule_nodes: set[str] = set()
    layering_nodes: set[str] = set()

    for crime in ground_truth.get("crimes", []):
        if crime["crime_type"] == "structuring":
            all_involved = set(crime["nodes_involved"])
            mule_id = str(crime["metadata"].get("mule_id", ""))
            mule_nodes.add(mule_id)
            structuring_sources = all_involved - mule_nodes
        elif crime["crime_type"] == "layering":
            layering_nodes.update(crime["nodes_involved"])

    # Build nodes — limit to first N for performance
    all_node_ids = sorted(str(n) for n in G.nodes())
    selected_ids = set(all_node_ids[:limit])

    # Always include ALL criminal nodes regardless of limit
    selected_ids.update(structuring_sources)
    selected_ids.update(mule_nodes)
    selected_ids.update(layering_nodes)

    nodes = []
    for sid in sorted(selected_ids):
        # Resolve node ID (FORGE uses int internally)
        resolved = None
        for candidate in [sid, int(sid) if sid.isdigit() else None]:
            if candidate is not None and candidate in G:
                resolved = candidate
                break
        if resolved is None:
            continue

        data = G.nodes.get(resolved, {})

        if sid in mule_nodes:
            group = "structuring_mule"
        elif sid in structuring_sources:
            group = "structuring_source"
        elif sid in layering_nodes:
            group = "layering"
        else:
            group = "legitimate"

        risk = data.get("risk_score", 0.5)
        nodes.append({
            "id": sid,
            "name": data.get("name", f"Entity {sid}"),
            "group": group,
            "entity_type": data.get("entity_type", "individual"),
            "risk_rating": "high" if risk > 0.7 else ("medium" if risk > 0.3 else "low"),
            "degree": G.degree(resolved),
        })

    # Build edges — only between selected nodes
    node_set = {n["id"] for n in nodes}
    edges = []
    for u, v, key, data in G.edges(keys=True, data=True):
        su, sv = str(u), str(v)
        if su in node_set and sv in node_set:
            amount = data.get("amount", 0)
            edges.append({
                "source": su,
                "target": sv,
                "label": data.get("label", "legitimate"),
                "amount": float(amount) if isinstance(amount, Decimal) else float(amount or 0),
                "currency": data.get("currency", "USD"),
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def get_node(node_id: str) -> dict[str, Any] | None:
    """Return detailed node information including crime classification."""
    state = get_state()
    if state.graph is None:
        return None

    G = state.graph
    resolved = None
    for candidate in [node_id, int(node_id) if node_id.isdigit() else None]:
        if candidate is not None and candidate in G:
            resolved = candidate
            break
    if resolved is None:
        return None

    data = G.nodes.get(resolved, {})
    sid = str(resolved)

    # Crime classification
    is_criminal = False
    crime_type = None
    for crime in state.ground_truth.get("crimes", []):
        if sid in crime["nodes_involved"]:
            is_criminal = True
            crime_type = crime["crime_type"]
            break

    risk = data.get("risk_score", 0.5)
    return {
        "id": sid,
        "name": data.get("name", f"Entity {sid}"),
        "entity_type": data.get("entity_type", "individual"),
        "jurisdiction": data.get("country", "US"),
        "risk_score": float(risk),
        "risk_rating": "high" if risk > 0.7 else ("medium" if risk > 0.3 else "low"),
        "degree": G.degree(resolved),
        "in_degree": G.in_degree(resolved),
        "out_degree": G.out_degree(resolved),
        "is_criminal": is_criminal,
        "crime_type": crime_type,
        "swift_code": data.get("swift", ""),
        "ifsc_code": data.get("ifsc_code", ""),
        "pan_number": data.get("pan_number", ""),
        "address": data.get("address", ""),
        "account_id": sid,
    }


def get_nodes(
    page: int = 1,
    per_page: int = 50,
    entity_type: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Paginated node listing with optional filters."""
    state = get_state()
    if state.graph is None:
        return {"nodes": [], "total": 0, "page": page, "per_page": per_page, "total_pages": 0}

    G = state.graph
    all_nodes = []
    for node_id in sorted(G.nodes(), key=str):
        node_data = get_node(str(node_id))
        if node_data is None:
            continue
        if entity_type and node_data["entity_type"] != entity_type:
            continue
        if search and search.lower() not in node_data["name"].lower() and search != str(node_id):
            continue
        all_nodes.append(node_data)

    total = len(all_nodes)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page

    return {
        "nodes": all_nodes[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


def get_transactions(node_id: str) -> list[dict[str, Any]]:
    """Return all transactions involving a node (inbound + outbound)."""
    state = get_state()
    if state.graph is None:
        return []

    G = state.graph
    resolved = None
    for candidate in [node_id, int(node_id) if node_id.isdigit() else None]:
        if candidate is not None and candidate in G:
            resolved = candidate
            break
    if resolved is None:
        return []

    txns = []
    for u, v, key, data in G.edges(keys=True, data=True):
        if u == resolved or v == resolved:
            amount = data.get("amount", 0)
            ts = data.get("timestamp", 0)
            if hasattr(ts, "timestamp"):
                ts = int(ts.timestamp())
            txns.append({
                "id": str(data.get("transaction_id", f"txn_{u}_{v}_{key}")),
                "source": str(u),
                "target": str(v),
                "amount": float(amount) if isinstance(amount, Decimal) else float(amount or 0),
                "currency": data.get("currency", "USD"),
                "transaction_type": str(data.get("transaction_type", "WIRE")).upper(),
                "timestamp": int(ts) if isinstance(ts, (int, float)) else 0,
                "label": data.get("label", "legitimate"),
            })

    return sorted(txns, key=lambda t: t["timestamp"], reverse=True)


def get_connections(node_id: str) -> list[dict[str, Any]]:
    """Return aggregated connections for a node."""
    state = get_state()
    if state.graph is None:
        return []

    G = state.graph
    resolved = None
    for candidate in [node_id, int(node_id) if node_id.isdigit() else None]:
        if candidate is not None and candidate in G:
            resolved = candidate
            break
    if resolved is None:
        return []

    connections: dict[str, dict] = {}
    for u, v, key, data in G.edges(keys=True, data=True):
        amount = data.get("amount", 0)
        if isinstance(amount, Decimal):
            amount = float(amount)
        else:
            amount = float(amount or 0)

        if v == resolved:
            peer = str(u)
            direction = "inbound"
        elif u == resolved:
            peer = str(v)
            direction = "outbound"
        else:
            continue

        conn_key = f"{peer}_{direction}"
        if conn_key not in connections:
            peer_data = G.nodes.get(u if direction == "inbound" else v, {})
            connections[conn_key] = {
                "node_id": peer,
                "name": peer_data.get("name", f"Entity {peer}"),
                "direction": direction,
                "transaction_count": 0,
                "total_amount": 0.0,
                "entity_type": peer_data.get("entity_type", ""),
            }
        connections[conn_key]["transaction_count"] += 1
        connections[conn_key]["total_amount"] += amount

    return sorted(connections.values(), key=lambda c: c["total_amount"], reverse=True)
