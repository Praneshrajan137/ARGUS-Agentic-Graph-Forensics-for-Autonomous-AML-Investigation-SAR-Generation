# Core module - Graph generation, crime injection, and A2A interface
"""
Core components for the Green Financial Crime Agent:
- graph_generator: NetworkX scale-free graph generation
- crime_injector: Structuring and Layering injection
- a2a_interface: Agent2Agent HTTP/JSON-RPC protocol
"""

from .graph_generator import *  # noqa: F403
from .crime_injector import *  # noqa: F403
from .a2a_interface import *  # noqa: F403

