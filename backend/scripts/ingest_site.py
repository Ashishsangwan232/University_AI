"""Build the college knowledge base from the public website.

    python scripts/ingest_site.py                    # www.lpu.in, 150 pages, depth 3
    python scripts/ingest_site.py --pages 40 --depth 2
    python scripts/ingest_site.py --url https://www.lpu.in/admission/
    python scripts/ingest_site.py --status          # what is stored right now
    python scripts/ingest_site.py --ask "hostel fee"  # try a search
    python scripts/ingest_site.py --clear           # empty the store

Runs the crawl in this process and prints each page as it is fetched, so a long
crawl is visible rather than a silent wait. The backend does not need to be
running; the store it writes is the one the backend reads.

Semantic search needs a local Ollama with the embedding model:

    ollama serve
    ollama pull embeddinggemma

Without it the pages are still stored and searched by keyword, and the output
says so.
"""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.rag.service import (  # noqa: E402
    clear_knowledge,
    ingest_website,
    knowledge_status,
    search_knowledge,
)


def show_status() -> None:
    status = knowledge_status()
    embeddings = status["embeddings"]
    print("=" * 70)
    print("COLLEGE KNOWLEDGE BASE")
    print("=" * 70)
    print(f"  pages stored     {status['pages']}")
    print(f"  passages         {status['chunks']}")
    print(f"  sites            {', '.join(status['sites']) or '(none)'}")
    if status["has_vectors"]:
        print(f"  vectors          yes, {status['dimensions']} dimensions")
        print("  search           " + (
            "hybrid over the whole store (numpy)" if status["fast_search"]
            else "keywords, reranked by meaning - `pip install numpy` to compare "
                 "the whole store at once"
        ))
    else:
        print("  vectors          none stored - keyword search only")
        print("  search           keywords only")
    print(f"  location         {status['location']}")
    print(f"  embedder         {embeddings['provider']} / {embeddings['model'] or '-'} "
          f"({'reachable' if embeddings['available'] else 'NOT reachable'})")
    if embeddings["provider"] == "ollama" and not embeddings["available"]:
        print(f"                   tried {embeddings['base_url']} - run `ollama serve`, then")
        print(f"                   `ollama pull {embeddings['model']}`")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="site to crawl (default: COLLEGE_WEBSITE_URL)")
    parser.add_argument("--pages", type=int, default=None, help="maximum pages to fetch")
    parser.add_argument("--depth", type=int, default=None, help="how many links deep to follow")
    parser.add_argument("--status", action="store_true", help="show what is stored and exit")
    parser.add_argument("--clear", action="store_true", help="empty the knowledge base and exit")
    parser.add_argument("--ask", default=None, help="search the knowledge base and exit")
    parser.add_argument("--quiet", action="store_true", help="do not print each page")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(message)s",
    )

    if args.clear:
        print(clear_knowledge())
        return 0

    if args.status:
        show_status()
        return 0

    if args.ask:
        found = search_knowledge(args.ask, limit=5)
        if not found.get("available"):
            print(found.get("message"))
            return 1
        print(f"\n{found['method']} over {found['searched_chunks']} passage(s)\n")
        if found.get("note"):
            print(f"  note: {found['note']}\n")
        for index, result in enumerate(found["results"], start=1):
            print(f"{index}. [{result['score']}] {result['title']}")
            if result["heading"]:
                print(f"   section: {result['heading']}")
            print(f"   {result['url']}")
            print(f"   {result['content'][:300]}...\n")
        if not found["results"]:
            print("  Nothing matched.")
        return 0

    target = args.url or settings.college_website_url
    print(f"Crawling {target}")
    print(f"  budget: {args.pages or settings.rag_crawl_max_pages} pages, "
          f"depth {args.depth if args.depth is not None else settings.rag_crawl_max_depth}, "
          f"{settings.rag_crawl_delay_seconds}s between requests")
    print("  This is polite by design and takes a few minutes.\n")

    try:
        result = ingest_website(target, max_pages=args.pages, max_depth=args.depth)
    except (ValueError, RuntimeError) as exc:
        print(f"\nIngest failed: {exc}")
        return 1

    print("\n" + "=" * 70)
    print(f"  {result['pages']} page(s) -> {result['chunks']} passage(s) in {result['seconds']}s")
    print(f"  embedded: {'yes' if result['embedded'] else 'no'} "
          f"({result['embedding_provider']} / {result['embedding_model'] or '-'})")
    if result["note"]:
        print(f"  note: {result['note']}")
    print("=" * 70)
    show_status()
    print("\nTry it:  python scripts/ingest_site.py --ask \"hostel fees\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
