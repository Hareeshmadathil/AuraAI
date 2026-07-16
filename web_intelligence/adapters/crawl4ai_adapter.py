"""Optional Crawl4AI public-evidence adapter boundary."""
import importlib.util
from web_intelligence.adapters.unavailable import UnavailableAdapter
from web_intelligence.enums import AdapterKind

PINNED_VERSION="0.9.1"
def create_crawl4ai_adapter():
    if importlib.util.find_spec("crawl4ai") is None:
        return UnavailableAdapter(AdapterKind.CRAWL4AI,"Crawl4AI is not installed; optional adapter remains unavailable.",PINNED_VERSION)
    return UnavailableAdapter(AdapterKind.CRAWL4AI,"Crawl4AI is installed but live execution requires an approved runtime injection.",PINNED_VERSION)
