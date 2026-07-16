"""Deterministic zero-argument composition root."""
from functools import lru_cache
from intelligence_director.fixtures import synthetic_signals
from intelligence_director.service import IntelligenceDirectorService
def create_demo_service()->IntelligenceDirectorService: return IntelligenceDirectorService()
@lru_cache(maxsize=1)
def create_demo_result(): return create_demo_service().analyze(synthetic_signals())
