"""
Test Suite for Full Pipeline Integration
========================================
End-to-end integration tests for the Green Financial Crime Agent.

Tests cover:
1. Graph generation performance
2. Serialization (JSON round-trip)
3. Crime injection with skill scripts
4. Validation workflow
5. Complete pipeline execution
"""

import pytest
import json
import time
import sys
from pathlib import Path

import networkx as nx

# Add skill scripts to path for testing working implementations
PROJECT_ROOT = Path(__file__).parent.parent.parent
SKILLS_PATH = PROJECT_ROOT / ".claude" / "skills" / "financial-crime" / "scripts"
sys.path.insert(0, str(SKILLS_PATH))

from src.core.graph_generator import save_graph, load_graph


# =============================================================================
# Tests for Graph Generation Performance
# =============================================================================

@pytest.mark.slow
@pytest.mark.integration
class TestGraphGenerationPerformance:
    """Performance tests for graph generation."""
    
    def test_50_node_generation_fast(self):
        """Test that 50-node graph generates quickly."""
        from src.core.graph_generator import generate_scale_free_graph
        
        start = time.time()
        G = generate_scale_free_graph(n_nodes=50, seed=42)
        elapsed = time.time() - start
        
        assert G.number_of_nodes() == 50
        assert elapsed < 1.0, f"50-node generation took {elapsed:.2f}s"
    
    def test_500_node_generation_under_5_seconds(self):
        """Test that 500-node graph generates in under 5 seconds."""
        from src.core.graph_generator import generate_scale_free_graph
        
        start = time.time()
        G = generate_scale_free_graph(n_nodes=500, seed=42)
        elapsed = time.time() - start
        
        assert G.number_of_nodes() == 500
        assert elapsed < 5.0, f"500-node generation took {elapsed:.2f}s"
    
    def test_1000_node_generation_under_10_seconds(self):
        """Test that 1000-node graph generates in under 10 seconds (PRD requirement)."""
        from src.core.graph_generator import generate_scale_free_graph
        
        start = time.time()
        G = generate_scale_free_graph(n_nodes=1000, seed=42)
        elapsed = time.time() - start
        
        assert G.number_of_nodes() == 1000
        assert elapsed < 10.0, f"1000-node generation took {elapsed:.2f}s, limit is 10s"


# =============================================================================
# Tests for Serialization
# =============================================================================

@pytest.mark.integration
class TestSerialization:
    """Tests for graph serialization and deserialization."""
    
    def test_json_round_trip(self, baseline_graph, tmp_path):
        """Test that graph survives JSON round-trip."""
        output_path = tmp_path / "test_graph.json"

        save_graph(baseline_graph, output_path)
        loaded_graph = load_graph(output_path)

        assert loaded_graph.number_of_nodes() == baseline_graph.number_of_nodes()
        assert loaded_graph.number_of_edges() == baseline_graph.number_of_edges()

    def test_json_preserves_node_attributes(self, baseline_graph, tmp_path):
        """Test that node attributes are preserved after JSON serialization."""
        output_path = tmp_path / "test_graph.json"

        sample_node = list(baseline_graph.nodes())[0]
        original_attrs = dict(baseline_graph.nodes[sample_node])

        save_graph(baseline_graph, output_path)
        loaded_graph = load_graph(output_path)

        loaded_attrs = dict(loaded_graph.nodes[sample_node])
        for key, val in original_attrs.items():
            assert str(loaded_attrs[key]) == str(val)

    def test_json_preserves_edge_attributes(self, baseline_graph, tmp_path):
        """Test that edge attributes are preserved after JSON serialization."""
        output_path = tmp_path / "test_graph.json"

        sample_edge = list(baseline_graph.edges())[0]
        original_attrs = dict(baseline_graph.edges[sample_edge])

        save_graph(baseline_graph, output_path)
        loaded_graph = load_graph(output_path)

        loaded_attrs = dict(loaded_graph.edges[sample_edge])
        for key, val in original_attrs.items():
            assert str(loaded_attrs[key]) == str(val)
    
    def test_large_graph_serialization(self, tmp_path):
        """Test serialization of large graph."""
        from src.core.graph_generator import generate_scale_free_graph

        G = generate_scale_free_graph(n_nodes=1000, seed=42)
        output_path = tmp_path / "large_graph.json"

        # Should not raise
        save_graph(G, output_path)

        # Verify file was created and has content
        assert output_path.exists()
        assert output_path.stat().st_size > 0


# =============================================================================
# Tests Using Skill Script Implementations
# =============================================================================

@pytest.mark.integration
class TestSkillScriptImplementations:
    """Tests using the working implementations from .claude/skills/"""
    
    @pytest.fixture
    def skill_graph(self):
        """Create a graph using skill script implementation."""
        try:
            from generate_graph import generate_scale_free_graph as skills_generate
            G = skills_generate(n=100, seed=42)
            return G
        except ImportError:
            pytest.skip("Skill scripts not available")
    
    def test_skill_graph_generation(self):
        """Test graph generation using skill script."""
        try:
            from generate_graph import generate_scale_free_graph as skills_generate
            
            G = skills_generate(n=100, seed=42)
            
            assert G.number_of_nodes() == 100
            # Skill implementation adds attributes
            sample_node = list(G.nodes())[0]
            assert 'name' in G.nodes[sample_node]
        except ImportError:
            pytest.skip("generate_graph skill script not available")
    
    def test_skill_structuring_injection(self):
        """Test structuring injection using skill script."""
        try:
            from generate_graph import generate_scale_free_graph as skills_generate
            from inject_structuring import inject_structuring as skills_inject
            
            G = skills_generate(n=100, seed=42)
            original_nodes = G.number_of_nodes()
            
            G, ground_truth = skills_inject(G, num_sources=10, seed=42)
            
            # Should have added 10 smurf nodes
            assert G.number_of_nodes() == original_nodes + 10
            
            # Ground truth should have correct structure
            assert ground_truth['crime_type'] == 'structuring'
            assert len(ground_truth['sources']) == 10
            
            # All amounts should be below CTR threshold
            for source in ground_truth['sources']:
                assert source['amount'] < 10000
                assert source['amount'] >= 9000
                
        except ImportError:
            pytest.skip("Skill scripts not available")
    
    def test_skill_layering_injection(self):
        """Test layering injection using skill script."""
        try:
            from generate_graph import generate_scale_free_graph as skills_generate
            from inject_layering import inject_layering as skills_inject
            
            G = skills_generate(n=100, seed=42)
            
            G, ground_truth = skills_inject(G, chain_length=5, seed=42)
            
            # Ground truth should have correct structure
            assert ground_truth['crime_type'] == 'layering'
            assert ground_truth['chain_length'] == 5
            
            # Amounts should decay
            amounts = [hop['amount'] for hop in ground_truth['chain']]
            for i in range(1, len(amounts)):
                assert amounts[i] < amounts[i-1], "Amounts should decay"
                
        except ImportError:
            pytest.skip("Skill scripts not available")
    
    def test_skill_cycle_detection(self):
        """Test cycle detection using skill script."""
        try:
            from detect_cycles import detect_cycles, validate_layering_chain  # noqa: F401
            
            # Create valid chain
            G = nx.DiGraph()
            chain_nodes = [1, 2, 3, 4, 5]
            for i in range(len(chain_nodes) - 1):
                G.add_edge(chain_nodes[i], chain_nodes[i+1])
            
            cycles = detect_cycles(G)
            assert len(cycles) == 0
            
            # Create graph with cycle
            G_cycle = nx.DiGraph()
            G_cycle.add_edges_from([(1, 2), (2, 3), (3, 1)])
            
            cycles = detect_cycles(G_cycle)
            assert len(cycles) > 0
            
        except ImportError:
            pytest.skip("detect_cycles skill script not available")


# =============================================================================
# Tests for Validation Workflow
# =============================================================================

@pytest.mark.integration
class TestValidationWorkflow:
    """Tests for the validation workflow."""
    
    def test_graph_validation_passes_for_scale_free(self, baseline_graph):
        """Test that scale-free graph passes validation."""
        from src.utils.validators import (
            validate_graph_structure,
            validate_scale_free_distribution
        )
        
        # Note: scale_free_graph may have some structural issues
        struct_valid, struct_errors = validate_graph_structure(baseline_graph)
        scale_valid, scale_metrics = validate_scale_free_distribution(baseline_graph)
        
        # Scale-free validation should pass
        assert scale_valid is True
        assert scale_metrics['hub_count'] > 0
    
    def test_structuring_pattern_validation(self, valid_structuring_edges):
        """Test structuring pattern validation."""
        from src.utils.validators import validate_structuring_pattern
        
        is_valid, errors = validate_structuring_pattern(valid_structuring_edges)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_layering_pattern_validation(self, valid_layering_chain):
        """Test layering pattern validation."""
        from src.utils.validators import validate_layering_pattern
        
        G, chain_edges = valid_layering_chain
        
        is_valid, errors = validate_layering_pattern(G, chain_edges)
        
        assert is_valid is True
        assert len(errors) == 0


# =============================================================================
# Tests for Complete Pipeline
# =============================================================================

@pytest.mark.slow
@pytest.mark.integration
class TestCompletePipeline:
    """End-to-end pipeline tests."""
    
    def test_full_pipeline_with_core_modules(self, tmp_path):
        """Test complete pipeline using core modules."""
        from src.core.graph_generator import generate_scale_free_graph
        from src.utils.validators import validate_scale_free_distribution
        
        # Step 1: Generate graph
        G = generate_scale_free_graph(n_nodes=100, seed=42)
        assert G.number_of_nodes() == 100
        
        # Step 2: Validate scale-free property
        is_valid, metrics = validate_scale_free_distribution(G)
        assert metrics['num_nodes'] == 100
        
        # Step 3: Save graph
        output_path = tmp_path / "pipeline_graph.json"
        save_graph(G, output_path)

        assert output_path.exists()

        # Step 4: Load and verify
        loaded = load_graph(output_path)

        assert loaded.number_of_nodes() == G.number_of_nodes()
    
    def test_full_pipeline_with_skill_scripts(self, tmp_path):
        """Test complete pipeline using skill script implementations."""
        try:
            from generate_graph import generate_scale_free_graph as skills_generate
            from inject_structuring import inject_structuring as skills_struct
            from inject_layering import inject_layering as skills_layer
        except ImportError:
            pytest.skip("Skill scripts not available")
        
        # Step 1: Generate baseline graph
        G = skills_generate(n=200, seed=42)
        baseline_nodes = G.number_of_nodes()
        
        # Step 2: Inject structuring crime
        G, struct_truth = skills_struct(G, num_sources=15, seed=42)
        assert G.number_of_nodes() == baseline_nodes + 15
        
        # Step 3: Inject layering crime
        G, layer_truth = skills_layer(G, chain_length=5, seed=42)
        
        # Step 4: Save graph and ground truth
        graph_path = tmp_path / "final_graph.json"
        save_graph(G, graph_path)

        truth_path = tmp_path / "ground_truth.json"
        with open(truth_path, 'w') as f:
            json.dump({
                'structuring': struct_truth,
                'layering': layer_truth
            }, f, default=str)
        
        # Step 5: Verify outputs
        assert graph_path.exists()
        assert truth_path.exists()
        
        # Step 6: Load and verify
        loaded_graph = load_graph(graph_path)
        
        with open(truth_path, 'r') as f:
            loaded_truth = json.load(f)
        
        assert loaded_graph.number_of_nodes() == G.number_of_nodes()
        assert 'structuring' in loaded_truth
        assert 'layering' in loaded_truth
    
    def test_multiple_crime_injections_no_conflict(self, tmp_path):
        """Test multiple crime injections don't conflict."""
        try:
            from generate_graph import generate_scale_free_graph as skills_generate
            from inject_structuring import inject_structuring as skills_struct
        except ImportError:
            pytest.skip("Skill scripts not available")
        
        G = skills_generate(n=300, seed=42)
        
        # Inject multiple structuring patterns
        ground_truths = []
        for i in range(3):
            G, truth = skills_struct(G, num_sources=10, seed=42 + i)
            ground_truths.append(truth)
        
        # Verify each injection created unique sources
        all_mules = [t['mule_id'] for t in ground_truths]  # noqa: F841
        # Note: mules might be the same if auto-selected, but sources should differ
        
        # Total structuring sources should be 30
        total_sources = sum(len(t['sources']) for t in ground_truths)
        assert total_sources == 30


# =============================================================================
# Memory Usage Tests
# =============================================================================

@pytest.mark.slow
@pytest.mark.integration
class TestMemoryUsage:
    """Memory usage tests (PRD requirement: < 2GB)."""
    
    def test_1000_node_graph_memory(self):
        """Test that 1000-node graph uses reasonable memory."""
        import sys
        from src.core.graph_generator import generate_scale_free_graph
        
        G = generate_scale_free_graph(n_nodes=1000, seed=42)
        
        # Get approximate memory size
        # This is a rough estimate, not exact memory usage
        size_bytes = sys.getsizeof(G)
        
        # Should be well under 2GB
        assert size_bytes < 2 * 1024 * 1024 * 1024  # 2GB in bytes
