"""Secret-safe provider inventory CLI; performs no provider calls."""
from __future__ import annotations
import argparse
from providers.composition import create_multi_llm_router
from providers.settings import MultiLLMSettings


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="List configured AuraAI text providers safely.")
    parser.add_argument("--list", action="store_true", dest="list_providers")
    args=parser.parse_args(argv)
    if not args.list_providers: parser.print_help(); return 0
    settings=MultiLLMSettings.from_environment(); state=create_multi_llm_router(settings).build_state()
    print(f"routing_mode={settings.mode.value}"); print(f"selected_default={settings.default_provider}")
    for health in state.health:
        if health.name == "deterministic": continue
        capabilities=",".join(value.value for value in health.capabilities)
        print(f"provider={health.name} configured={str(health.configured).lower()} available={str(health.status == 'available').lower()} capabilities={capabilities}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
