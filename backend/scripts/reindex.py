"""CLI entrypoint for a manual scrape + index pass:

    python -m backend.scripts.reindex [frequent|slow] [--incremental]
    python -m backend.scripts.reindex --scraper finki_hub.sessions
    python -m backend.scripts.reindex --list

Same as the admin panel's Reindex button, but works without the API running.
No cadence = all scrapers. `--incremental` only fetches new URLs, so it won't pick up
edited pages.
"""

import argparse
import logging

from backend.ingestion.pipeline import run_ingestion
from backend.scrapers.registry import SCRAPERS

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m backend.scripts.reindex")
    parser.add_argument(
        "cadence",
        nargs="?",
        choices=["frequent", "slow"],
        help="limit to this cadence group; ignored (and unnecessary) when --scraper is given",
    )
    parser.add_argument(
        "--scraper",
        metavar="NAME",
        help="limit to exactly this scraper by name, regardless of cadence — see --list",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="only fetch URLs not already in the database (skips edit detection)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print every scraper name (for use with --scraper) and exit",
    )
    args = parser.parse_args()

    if args.list:
        for entry in SCRAPERS:
            print(f"{entry.name}  (source={entry.source}, cadence={entry.cadence}, enabled={entry.enabled})")
        return

    stats = run_ingestion(None if args.scraper else args.cadence, incremental=args.incremental, name=args.scraper)
    print(stats)


if __name__ == "__main__":
    main()
