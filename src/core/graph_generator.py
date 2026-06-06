"""
Graph Generator Module
======================
Generates scale-free financial transaction graphs using NetworkX.

Technical Specification:
- Algorithm: Barabási-Albert scale-free graph
- Parameters: alpha=0.41, beta=0.54, gamma=0.05
- Target: 1,000 nodes, 10,000 edges
- Performance: < 10 seconds generation time

v8.0: Decimal-everywhere for all currency amounts.
      CRITICAL: All edge amounts are Decimal(str(value)), NEVER float.
v7.0: Initial implementation with locale-aligned generation.
"""

import networkx as nx
from typing import Iterator, List, MutableMapping, Optional, Union
from decimal import Decimal
import random
import json
import logging
import warnings
from pathlib import Path
from datetime import datetime, timedelta
from faker import Faker

logger = logging.getLogger(__name__)

# SDV import with graceful fallback
# We need to check if SDV is actually installed, not just if our module imports
try:
    import sdv  # noqa: F401
    from .sdv_models import get_transaction_synthesizer
    SDV_AVAILABLE = True
    logger.info("SDV successfully imported for correlated data generation")
except ImportError as e:
    SDV_AVAILABLE = False
    get_transaction_synthesizer = None  # type: ignore[assignment,no-redef]
    logger.warning(f"SDV not available, using random fallback: {e}")


# Country code to Faker locale mapping (CORRECTED)
COUNTRY_TO_LOCALE = {
    'US': 'en_US',
    'GB': 'en_GB',
    'IN': 'en_IN',
    'DE': 'de_DE',
    'FR': 'fr_FR',
    'IT': 'it_IT',
    'ES': 'es_ES',
    'JP': 'ja_JP',
    'CN': 'zh_CN',
    'BR': 'pt_BR',
    'CA': 'en_CA',
    'AU': 'en_AU',
    'NL': 'nl_NL',
    'CH': 'de_CH',
    'SE': 'sv_SE',
    'NO': 'nb_NO',  # Norwegian Bokmål (CORRECTED from 'no_NO')
    'DK': 'da_DK',  # Danish (CORRECTED from 'dk_DK')
    'PL': 'pl_PL',
    'RU': 'ru_RU',
    'TR': 'tr_TR',
}

# Supported countries for entity generation
SUPPORTED_COUNTRIES = ['US', 'GB', 'IN', 'DE', 'FR', 'IT', 'ES', 'JP']


_faker_cache: dict[str, Faker] = {}


def get_localized_faker(country_code: str) -> Faker:
    """
    Return a Faker instance locked to the specified country's locale.

    Uses a module-level cache to avoid creating thousands of Faker instances
    (only 8 unique locales exist). Saves ~100MB RAM on constrained deployments.

    Args:
        country_code: ISO 3166-1 alpha-2 country code

    Returns:
        Faker instance configured for that country's locale
    """
    locale = COUNTRY_TO_LOCALE.get(country_code, 'en_US')
    if locale not in _faker_cache:
        _faker_cache[locale] = Faker(locale)
    return _faker_cache[locale]


def generate_scale_free_graph(
    n_nodes: int = 1000,
    alpha: float = 0.41,
    beta: float = 0.54,
    gamma: float = 0.05,
    seed: Optional[int] = None
) -> nx.MultiDiGraph:
    """
    Generate a scale-free directed graph representing a financial network.
    
    Args:
        n_nodes: Number of nodes (entities) in the graph
        alpha: Probability for adding a new node connected to an existing node
        beta: Probability for adding an edge between two existing nodes
        gamma: Probability for adding a new node connected from an existing node
        seed: Random seed for reproducibility
    
    Returns:
        NetworkX MultiDiGraph representing the financial network
    
    Raises:
        ValueError: If alpha + beta + gamma != 1.0
    """
    # Validate parameters sum to 1.0
    if abs(alpha + beta + gamma - 1.0) > 1e-9:
        raise ValueError(f"alpha + beta + gamma must equal 1.0, got {alpha + beta + gamma}")
    
    # Generate scale-free graph
    G = nx.scale_free_graph(n=n_nodes, alpha=alpha, beta=beta, gamma=gamma, seed=seed)
    
    return G


def _iter_edge_data(
    G: nx.DiGraph | nx.MultiDiGraph,
) -> Iterator[MutableMapping[str, object]]:
    """Yield mutable edge attribute mappings for DiGraph and MultiDiGraph."""
    if isinstance(G, nx.MultiDiGraph):
        for _, _, _, data in G.edges(keys=True, data=True):
            yield data
    else:
        for _, _, data in G.edges(data=True):
            yield data


def add_entity_attributes(
    G: nx.DiGraph | nx.MultiDiGraph,
    faker_instance=None,  # DEPRECATED - ignored for locale safety
    locales: Optional[List[str]] = None,  # DEPRECATED - ignored for locale safety
    seed: Optional[int] = None
) -> nx.DiGraph | nx.MultiDiGraph:
    """
    Add entity attributes with LOCALE-ALIGNED generation.
    
    CRITICAL FIX: We now generate country FIRST, then use a locale-locked
    Faker to ensure SWIFT codes and IBANs match the jurisdiction.
    
    Args:
        G: NetworkX DiGraph or MultiDiGraph
        faker_instance: DEPRECATED (ignored for locale safety)
        locales: DEPRECATED (ignored for locale safety)
        seed: Random seed for reproducibility
    
    Returns:
        Graph with locale-consistent entity attributes
    """
    rng = random.Random(seed)
    local_fakers: dict[str, Faker] = {}

    entity_types = ['person', 'company', 'bank']
    entity_weights = [0.7, 0.25, 0.05]
    
    for node in G.nodes():
        # Step 1: Select country FIRST
        country = rng.choice(SUPPORTED_COUNTRIES)
        
        # Step 2: Get locale-locked Faker for that country
        if seed is None:
            fake = get_localized_faker(country)
        else:
            locale = COUNTRY_TO_LOCALE.get(country, 'en_US')
            if locale not in local_fakers:
                fake = Faker(locale)
                fake.seed_instance(seed + sorted(COUNTRY_TO_LOCALE.values()).index(locale))
                local_fakers[locale] = fake
            fake = local_fakers[locale]
        
        # Step 3: Generate all attributes using THIS locale
        entity_type = rng.choices(entity_types, weights=entity_weights)[0]
        G.nodes[node]['entity_type'] = entity_type
        G.nodes[node]['country'] = country  # Set BEFORE other attributes
        
        if entity_type == 'person':
            G.nodes[node]['name'] = fake.name()
        elif entity_type == 'company':
            G.nodes[node]['name'] = fake.company()
        else:  # bank
            G.nodes[node]['name'] = f"{fake.company()} Bank"
        
        # Generate locale-specific attributes
        G.nodes[node]['address'] = fake.address().replace('\n', ', ')
        
        # CRITICAL: SWIFT codes - use locale-specific with fallback
        # SWIFT format: 4 bank code + 2 country code + 2 location + optional 3 branch
        try:
            G.nodes[node]['swift'] = fake.swift()
        except AttributeError:
            # Fallback if locale doesn't support SWIFT
            # CORRECTED: Country code at positions 5-6, not at start
            G.nodes[node]['swift'] = f"XXXX{country}XX"
        
        # IBAN generation with fallback
        try:
            G.nodes[node]['iban'] = fake.iban()
        except AttributeError:
            # Fallback if locale doesn't support IBAN
            G.nodes[node]['iban'] = f"{country}{rng.randint(10000000, 99999999)}"
        
        G.nodes[node]['risk_score'] = round(rng.uniform(0, 1), 2)
        G.nodes[node]['verification_status'] = 'verified'
    
    logger.info(f"Locale-aligned entities: {G.number_of_nodes()} nodes across {len(SUPPORTED_COUNTRIES)} countries")
    return G


def add_transaction_attributes(
    G: nx.DiGraph | nx.MultiDiGraph,
    seed: Optional[int] = None,
    base_time: Optional[datetime] = None,
    use_sdv: bool = True
) -> nx.DiGraph | nx.MultiDiGraph:
    """
    Add transaction attributes to graph edges using SDV Gaussian Copula.
    
    This function uses SDV for statistically correlated data generation when available,
    with automatic fallback to random generation if SDV is not installed.
    
    SDV Correlation Rules:
    - High risk entities have larger transaction amounts
    - International transfers are systematically larger
    - Transaction types correlate with realistic spending patterns
    
    Args:
        G: NetworkX DiGraph or MultiDiGraph
        seed: Random seed for reproducibility
        base_time: Base timestamp for transactions (default: now)
        use_sdv: Whether to use SDV for correlated generation (default: True)
    
    Returns:
        Graph with transaction attributes added to edges
    """
    if base_time is None:
        base_time = datetime.now()
    
    num_edges = G.number_of_edges()
    
    # Use SDV if available and requested
    if use_sdv and SDV_AVAILABLE and num_edges > 0:
        return _add_transaction_attributes_sdv(G, num_edges, base_time, seed)
    else:
        return _add_transaction_attributes_random(G, base_time, seed)


def _add_transaction_attributes_sdv(
    G: nx.DiGraph | nx.MultiDiGraph,
    num_edges: int,
    base_time: datetime,
    seed: Optional[int] = None
) -> nx.DiGraph | nx.MultiDiGraph:
    """
    Add transaction attributes using SDV Gaussian Copula synthesizer.
    
    Generates statistically correlated transaction data where:
    - Amount correlates with risk_score
    - International transactions have higher amounts
    - Transaction types follow realistic distributions
    
    Reproducibility Strategy:
    SDV doesn't support seed parameter in sample(). We use an oversample-and-shuffle
    approach: generate a larger pool of samples, then use the seed to deterministically
    shuffle and select rows. This ensures different seeds produce different but 
    reproducible outputs.
    """
    # Get the trained synthesizer
    synthesizer = get_transaction_synthesizer()
    
    # Generate synthetic transaction data in batch
    logger.info(f"Generating {num_edges} synthetic transactions via SDV Gaussian Copula...")
    
    # CRITICAL: Oversample-and-shuffle approach for seed-based differentiation
    # SDV's reset_sampling() resets to a fixed state, so we:
    # 1. Reset to get deterministic base samples
    # 2. Sample MORE rows than needed (2x or minimum 1000)
    # 3. Use seed to shuffle and select the rows we need
    # This ensures different seeds produce different outputs
    
    synthesizer.reset_sampling()
    
    # Oversample: generate more rows than needed for variety
    oversample_size = max(num_edges + 500, 1000)
    synthetic_pool = synthesizer.sample(num_rows=oversample_size)
    
    # Use seed to deterministically shuffle and select
    rng = random.Random(seed)
    # Shuffle the pool using the seed
    indices = list(range(len(synthetic_pool)))
    rng.shuffle(indices)
    
    # Select the first num_edges rows from shuffled indices
    selected_indices = indices[:num_edges]
    synthetic_tx = synthetic_pool.iloc[selected_indices].reset_index(drop=True)
    
    # Convert to list of dicts for iteration
    tx_data = synthetic_tx.to_dict('records')
    
    # Assign to edges
    for edge_idx, data in enumerate(_iter_edge_data(G)):
        tx = tx_data[edge_idx]

        # Use seeded random hex instead of uuid.uuid4() for reproducibility
        data['transaction_id'] = f"txn_{rng.getrandbits(32):08x}"
        # Clamp amount to valid range [100, 50000] -- Decimal(str()) for safety
        raw_amount = max(100.0, min(float(tx['amount']), 50000.0))
        data['amount'] = Decimal(str(round(raw_amount, 2)))
        data['risk_score'] = float(tx['risk_score'])
        data['is_international'] = bool(tx['is_international'])
        data['currency'] = 'USD'
        data['timestamp'] = base_time - timedelta(days=rng.randint(0, 365))
        data['transaction_type'] = str(tx['transaction_type'])
        data['label'] = 'legitimate'
        data['memo'] = None
    
    logger.info(f"SDV transaction attributes assigned to {num_edges} edges")
    return G


def _add_transaction_attributes_random(
    G: nx.DiGraph | nx.MultiDiGraph,
    base_time: datetime,
    seed: Optional[int] = None
) -> nx.DiGraph | nx.MultiDiGraph:
    """
    Add transaction attributes using random generation (fallback method).
    
    This is the original implementation used when SDV is not available.
    
    Args:
        G: NetworkX graph
        base_time: Base timestamp for transactions
        seed: Random seed for reproducibility
    """
    transaction_types = ['wire', 'ach', 'cash', 'internal']
    
    logger.info("Using random fallback for transaction attributes (SDV not available)")
    
    # Create seeded RNG for reproducibility
    rng = random.Random(seed)
    
    for data in _iter_edge_data(G):
        data['transaction_id'] = f"txn_{rng.getrandbits(32):08x}"
        data['amount'] = Decimal(str(round(rng.uniform(100, 50000), 2)))
        data['currency'] = 'USD'
        data['timestamp'] = base_time - timedelta(days=rng.randint(0, 365))
        data['transaction_type'] = rng.choice(transaction_types)
        data['label'] = 'legitimate'
        data['memo'] = None
    
    return G


def save_graph(graph: nx.DiGraph | nx.MultiDiGraph, filepath: Union[str, 'Path']) -> None:
    """
    Save graph to JSON file (node-link format).

    Args:
        graph: NetworkX graph to save
        filepath: Output file path (.json extension recommended)
    """
    logger.info(f"Saving graph to {filepath}")
    data = nx.node_link_data(graph, edges="links")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, default=str, ensure_ascii=False)
    logger.info(f"Graph saved successfully ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")


def load_graph(filepath: Union[str, 'Path']) -> nx.DiGraph | nx.MultiDiGraph:
    """
    Load graph from JSON file (node-link format).
    Falls back to pickle for legacy .pkl files with a security warning.
    Only load legacy pickle files that were produced by trusted ARGUS runs.

    Args:
        filepath: Input file path

    Returns:
        Loaded NetworkX graph
    """
    filepath = Path(filepath)
    logger.info(f"Loading graph from {filepath}")
    if filepath.suffix == '.pkl':
        warnings.warn(
            f"Loading pickle file '{filepath}' — pickle deserialization can execute "
            "arbitrary code. Only load .pkl files you generated yourself. "
            "Migrate to JSON with save_graph().",
            stacklevel=2,
        )
        import pickle  # noqa: S403 — legacy fallback only
        with open(filepath, 'rb') as f:
            graph = pickle.load(f)  # noqa: S301
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        graph = nx.node_link_graph(data, edges="links")
    logger.info(f"Graph loaded successfully ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")
    return graph


__all__ = [
    'generate_scale_free_graph',
    'add_entity_attributes',
    'add_transaction_attributes',
    'save_graph',
    'load_graph',
    'get_localized_faker',
    'COUNTRY_TO_LOCALE',
    'SUPPORTED_COUNTRIES'
]
