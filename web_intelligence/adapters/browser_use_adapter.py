"""Optional Browser Use interactive read-only boundary."""
import importlib.util
from web_intelligence.adapters.unavailable import UnavailableAdapter
from web_intelligence.enums import AdapterKind

PINNED_VERSION="0.13.4"
LOW_MEMORY_FLAGS=("--disable-extensions","--disable-background-networking","--disable-sync","--no-first-run","--disable-dev-shm-usage")
def create_browser_use_adapter():
    if importlib.util.find_spec("browser_use") is None:
        return UnavailableAdapter(AdapterKind.BROWSER_USE,"Browser Use is not installed; optional adapter remains unavailable.",PINNED_VERSION)
    return UnavailableAdapter(AdapterKind.BROWSER_USE,"Browser Use is installed but interactive execution requires a disposable headful session injection.",PINNED_VERSION)
