"""Optional Crawl4AI public-evidence adapter boundary."""
from collections.abc import Callable
from importlib import metadata
import importlib.util

from web_intelligence.adapters.unavailable import UnavailableAdapter
from web_intelligence.enums import AdapterKind
from web_intelligence.exceptions import WebIntelligenceError
from web_intelligence.models import AdapterRequest, AdapterResult, AdapterStatus

PINNED_VERSION = "0.9.1"
INSTALLED_REASON = (
    "Crawl4AI is installed; live execution requires approved runtime injection."
)

CrawlRuntime = Callable[[AdapterRequest], AdapterResult]


class InstalledCrawl4AIAdapter:
    """Represent an installed package without implicitly enabling execution."""

    def __init__(self, version: str, reason: str, runtime: CrawlRuntime | None = None):
        self._runtime = runtime
        self.status = AdapterStatus(
            kind=AdapterKind.CRAWL4AI,
            available=True,
            reason=reason,
            version=version,
            external_operations_enabled=runtime is not None,
        )

    def execute(self, request: AdapterRequest) -> AdapterResult:
        """Use only an explicitly injected and separately approved runtime."""

        if self._runtime is None:
            raise WebIntelligenceError(
                self.status.reason,
                error_code="CRAWL4AI_RUNTIME_REQUIRED",
            )
        return self._runtime(request)


def _installed_version() -> str:
    """Read package metadata without importing Crawl4AI or launching a browser."""

    try:
        return metadata.version("crawl4ai")
    except metadata.PackageNotFoundError:
        return "unknown"


def create_crawl4ai_adapter(
    runtime: CrawlRuntime | None = None,
) -> UnavailableAdapter | InstalledCrawl4AIAdapter:
    """Create a detection-only adapter unless a runtime is explicitly injected."""

    if importlib.util.find_spec("crawl4ai") is None:
        return UnavailableAdapter(
            AdapterKind.CRAWL4AI,
            "Crawl4AI is not installed; optional adapter remains unavailable.",
            PINNED_VERSION,
        )

    installed_version = _installed_version()
    reason = INSTALLED_REASON
    if installed_version != PINNED_VERSION:
        reason = (
            f"Crawl4AI {installed_version} is installed; pinned version is "
            f"{PINNED_VERSION}; live execution requires approved runtime injection."
        )
    return InstalledCrawl4AIAdapter(installed_version, reason, runtime)
