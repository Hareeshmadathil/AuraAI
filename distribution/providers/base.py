"""Provider-neutral contract for local distribution preparation."""

from __future__ import annotations

from typing import Protocol

from creative_quality.models import CreativeQualityPackage
from distribution.models import DistributionPackage
from production.models import ProductionPackage


class DistributionProvider(Protocol):
    """Build a local package without authenticating or publishing."""

    def prepare_package(
        self,
        source: CreativeQualityPackage | ProductionPackage,
    ) -> DistributionPackage: ...
