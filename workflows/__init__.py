"""
Football Betting Intelligence System — Workflow Orchestration Package.

Multi-agent pipeline for professional football betting analysis.
"""

__version__ = "1.0.0"
__author__ = "Football Betting Intelligence System"

from .orchestration import Orchestrator, AgentRunner
from .pre_match_pipeline import PreMatchPipeline
from .live_match_pipeline import LiveMatchPipeline

__all__ = [
    "Orchestrator",
    "AgentRunner",
    "PreMatchPipeline",
    "LiveMatchPipeline",
]
