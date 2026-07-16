"""Pure composition helpers for deterministic connector construction."""
from pathlib import Path
from production_connector.loader import MissionPackageLoader
from production_connector.service import ProductionConnectorService


def create_demo_service() -> ProductionConnectorService:
    """Create a zero-argument, offline Mission Zero connector service."""
    root = Path(__file__).resolve().parents[1]
    package = root / "outputs" / "mission-zero-revision" / "f7385664-ac50-4e16-83c1-339781135a0a"
    return ProductionConnectorService(MissionPackageLoader(root).load(package))
