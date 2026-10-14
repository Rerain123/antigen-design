"""Deterministic, offline-only backend for the T-01 Phase 1 mock."""

from .acceptance import AcceptanceHarness, AssertionOperatorRegistry, SelectorAdapter
from .catalog import SpecificationBundle
from .engine import MockBackend, SubmissionResult
from .fixtures import FixtureMaterializer, FixtureRepository
from .tools import MockToolFacade

__all__ = [
    "AcceptanceHarness",
    "AssertionOperatorRegistry",
    "FixtureMaterializer",
    "FixtureRepository",
    "MockBackend",
    "MockToolFacade",
    "SelectorAdapter",
    "SpecificationBundle",
    "SubmissionResult",
]

__version__ = "0.1.0"
