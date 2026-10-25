"""Offline tests for the knowledge base and for chat memory.

No network, no crawl, no model, no database. Every case replays HTML or a
transcript, so the whole pipeline can be checked before pointing it at a real
site.

    python scripts/test_rag.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.rag.chunker import chunk_page, split_sections  # noqa: E402
from app.rag.crawler import (  # noqa: E402
    CrawledPage,
    extract_page,
    is_crawlable,
    normalise_url,
    same_site,
    strip_boilerplate,
)
from app.rag.search import bm25_scores, build_bm25, rank, tokenise  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(label: str, got, want) -> None:
    global PASSED
    if got == want:
        PASSED += 1
    else:
        FAILED.append(f"{label}\n    got:  {got!r}\n    want: {want!r}")


def truthy(label: str, got) -> None:
    check(label, bool(got), True)


HOST = "www.lpu.in"

# --------------------------------------------------------------------------
# URLs. One page must be fetched once, not once per spelling.
# --------------------------------------------------------------------------
check("a fragment is dropped",
      normalise_url("https://www.lpu.in/admission/#apply"), "https://www.lpu.in/admission")
check("a trailing slash is dropped",
      normalise_url("https://www.lpu.in/admission/"), "https://www.lpu.in/admission")
check("the host is lowercased",
      normalise_url("https://WWW.LPU.IN/Hostel"), "https://www.lpu.in/Hostel")
check("tracking parameters are dropped",
      normalise_url("https://www.lpu.in/x?utm_source=fb&id=7"), "https://www.lpu.in/x?id=7")
check("a real query is kept",
      normalise_url("https://www.lpu.in/p?id=7"), "https://www.lpu.in/p?id=7")
check("doubled slashes are collapsed",
      normalise_url("https://www.lpu.in//a//b"), "https://www.lpu.in/a/b")
check("the root keeps its slash", normalise_url("https://www.lpu.in/"), "https://www.lpu.in/")
check("junk is refused", normalise_url("not a url"), "")

check("the site itself", same_site("https://www.lpu.in/x", HOST), True)
check("a subdomain counts", same_site("https://admission.lpu.in/x", HOST), True)
check("the bare domain counts", same_site("https://lpu.in/x", HOST), True)
check("another site does not", same_site("https://www.facebook.com/lpu", HOST), False)
# The trap: a domain that merely ends with the same letters.
check("a look-alike domain does not", same_site("https://notlpu.in/x", HOST), False)

check("a page is crawlable", is_crawlable("https://www.lpu.in/admission", HOST), True)
check("a PDF is not", is_crawlable("https://www.lpu.in/files/fees.pdf", HOST), False)
check("an image is not", is_crawlable("https://www.lpu.in/img/a.jpg", HOST), False)
check("a login page is not", is_crawlable("https://www.lpu.in/login", HOST), False)
check("search results are not", is_crawlable("https://www.lpu.in/search?q=x", HOST), False)
check("endless pagination is not", is_crawlable("https://www.lpu.in/news/page/7", HOST), False)
check("an off-site link is not", is_crawlable("https://twitter.com/lpu", HOST), False)
check("a mailto is not", is_crawlable("mailto:info@lpu.in", HOST), False)

# --------------------------------------------------------------------------
# Page extraction. The chrome must not end up in the knowledge base.
# --------------------------------------------------------------------------
HTML = """
<html><head>
  <title>Hostel Facilities | LPU</title>
  <meta name="description" content="Accommodation at LPU.">
</head><body>
  <nav>Home Admissions Programmes Contact</nav>
  <div class="cookie-banner">We use cookies. Accept</div>
  <main>
    <h1>Hostel Facilities</h1>
    <p>The university provides separate hostels for boys and girls with
       air-conditioned and non air-conditioned rooms available on campus.</p>
    <h2>Hostel Fees</h2>
    <p>Hostel charges depend on the room type selected and are payable per term
       before the start of the academic session each year.</p>
  </main>
  <footer>Copyright LPU. All rights reserved.</footer>
  <script>var x = 1;</script>
</body></html>
"""
title, description, text, headings = extract_page(HTML, "https://www.lpu.in/hostel")
check("the title is read", title, "Hostel Facilities | LPU")
check("the meta description is read", description, "Accommodation at LPU.")
truthy("the content survives", "separate hostels for boys and girls" in text)
check("the navigation is gone", "Admissions Programmes Contact" in text, False)
check("the cookie banner is gone", "We use cookies" in text, False)
check("the footer is gone", "All rights reserved" in text, False)
check("the script is gone", "var x" in text, False)
check("headings are collected", headings, ["Hostel Facilities", "Hostel Fees"])

check("an empty document yields nothing", extract_page("<html></html>", "u")[2], "")

# --------------------------------------------------------------------------
# Boilerplate that survives extraction is found across the crawl instead.
# --------------------------------------------------------------------------
pages = [
    CrawledPage(url=f"https://www.lpu.in/p{index}", title=f"Page {index}",
                text=f"Apply Now\nCall 1800-102-4431\nThis is the real content of page {index}.")
    for index in range(10)
]
strip_boilerplate(pages)
check("a line on every page is removed", "Apply Now" in pages[0].text, False)
check("so is the repeated phone number", "1800-102-4431" in pages[3].text, False)
truthy("the page's own content stays", "real content of page 3" in pages[3].text)

# Below five pages there is nothing to compare, so nothing is removed.
few = [CrawledPage(url="u", title="t", text="Apply Now\nreal content")]
strip_boilerplate(few)
truthy("a tiny crawl is left alone", "Apply Now" in few[0].text)

# --------------------------------------------------------------------------
# Chunking on the page's own structure.
# --------------------------------------------------------------------------
sections = split_sections(
    "Hostel Fees\n"
    "Charges depend on the room type selected and are payable per term before the session.\n"
    "Mess Charges\n"
    "The mess is compulsory for residents and is billed separately each term of the year."
)
check("two sections were found", len(sections), 2)
check("the first heading", sections[0][0], "Hostel Fees")
check("the second heading", sections[1][0], "Mess Charges")

chunks = chunk_page({
    "url": "https://www.lpu.in/hostel",
    "title": "Hostel Facilities",
    "text": "Hostel Fees\nCharges depend on the room type selected and are payable per term.",
}, size=400, overlap=50)
check("one chunk from a short section", len(chunks), 1)
check("the chunk keeps its URL", chunks[0]["url"], "https://www.lpu.in/hostel")
check("the chunk knows its section", chunks[0]["heading"], "Hostel Fees")
check("and carries the trail", chunks[0]["trail"], "Hostel Facilities > Hostel Fees")
truthy("the searched text includes the trail", "Hostel Facilities" in chunks[0]["content"])
truthy("the displayed passage does not repeat it", chunks[0]["passage"].startswith("Charges"))

# A long section is split, and the split overlaps so a fact on the boundary is
# still findable from either side.
long_text = "Section\n" + " ".join(
    f"Sentence number {index} about hostel accommodation and fees." for index in range(60)
)
many = chunk_page({"url": "u", "title": "t", "text": long_text}, size=400, overlap=80)
truthy("a long section becomes several chunks", len(many) > 3)
truthy("every chunk stays near the size limit", all(len(c["passage"]) <= 700 for c in many))
check("chunks are numbered", [c["chunk_index"] for c in many[:3]], [0, 1, 2])

check("a page with no text yields nothing", chunk_page({"url": "u", "title": "t", "text": ""}), [])
# When there is no body at all, the meta description is better than nothing.
described = chunk_page({"url": "u", "title": "Fees", "text": "", "description": "What LPU charges."})
check("the description is used as a last resort", len(described), 1)

# --------------------------------------------------------------------------
# Ranking. Keyword search must work with no vectors at all.
# --------------------------------------------------------------------------
CORPUS = [
    {"url": "https://www.lpu.in/hostel", "title": "Hostel", "heading": "Fees",
     "content": "Hostel fees depend on room type and are payable per term.",
     "passage": "Hostel fees depend on room type and are payable per term."},
    {"url": "https://www.lpu.in/placements", "title": "Placements", "heading": "",
     "content": "Companies visit the campus each year for placement drives.",
     "passage": "Companies visit the campus each year for placement drives."},
    {"url": "https://www.lpu.in/admission", "title": "Admission", "heading": "",
     "content": "Admission is through the LPUNEST entrance examination.",
     "passage": "Admission is through the LPUNEST entrance examination."},
]

check("stopwords are dropped", tokenise("what is the hostel fee"), ["hostel", "fee"])
scores = bm25_scores(build_bm25(CORPUS), "hostel fees")
check("the hostel page scores highest", scores.index(max(scores)), 0)
check("an unrelated query scores nothing", max(bm25_scores(build_bm25(CORPUS), "quantum physics")), 0.0)

results, method = rank(CORPUS, "hostel fees", None, None, limit=3)
check("keyword-only is reported honestly", method, "keywords only")
check("the right page comes first", results[0]["url"], "https://www.lpu.in/hostel")
truthy("results carry their URL", all(result["url"] for result in results))
check("an empty store returns nothing", rank([], "x", None, None, 3), ([], "empty"))
check("a query matching nothing returns nothing", rank(CORPUS, "quantum physics", None, None, 3)[0], [])

# One passage per page, so five results are five sources.
DUPLICATED = CORPUS + [dict(CORPUS[0], passage="Hostel fees again", content="Hostel fees again")]
deduped, _ = rank(DUPLICATED, "hostel fees", None, None, limit=5)
check("the same page appears once", len([r for r in deduped if "hostel" in r["url"]]), 1)

# --------------------------------------------------------------------------
# The store must keep a finished embedding run. numpy is a speed-up, never a
# requirement - an earlier build wrote the matrix with numpy.save and threw
# away 467 seconds of embedding on a machine that did not have it.
# --------------------------------------------------------------------------
import os  # noqa: E402
import tempfile  # noqa: E402

os.environ["RAG_STORE_DIR"] = tempfile.mkdtemp()
import importlib  # noqa: E402

from app.rag import store as _store  # noqa: E402

importlib.reload(_store)

SAMPLE = [
    {"url": f"https://www.lpu.in/p{i}", "title": f"Page {i}", "heading": "",
     "content": f"passage {i}", "passage": f"passage {i}"}
    for i in range(4)
]
SAMPLE_VECTORS = [[float(i + 1), 2.0, 3.0] for i in range(4)]

meta = _store.save(SAMPLE, SAMPLE_VECTORS)
check("the store records the vector size", meta["dimensions"], 3)
check("and that vectors exist", meta["vectors"], True)

stored_chunks, stored_vectors = _store.load()
check("chunks come back", len(stored_chunks), 4)
truthy("vectors come back too", stored_vectors is not None)
check("one row per chunk", len(stored_vectors), 4)
row = list(stored_vectors.row(0))
check("rows are unit length", round(sum(v * v for v in row) ** 0.5, 5), 1.0)

# Re-crawling a site replaces it and its subdomains, and nothing else.
_store.save(
    SAMPLE + [{"url": "https://admission.lpu.in/x", "title": "Sub", "content": "s", "passage": "s"},
              {"url": "https://other.org/y", "title": "Other", "content": "o", "passage": "o"}],
    SAMPLE_VECTORS + [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
)
_store.replace_site(
    "lpu.in",
    [{"url": "https://www.lpu.in/fresh", "title": "Fresh", "content": "f", "passage": "f"}],
    [[0.5, 0.5, 0.5]],
)
after, after_vectors = _store.load()
urls = [chunk["url"] for chunk in after]
check("the old pages are gone", any("/p0" in url for url in urls), False)
check("so are the old subdomain pages", any("admission.lpu.in" in url for url in urls), False)
truthy("another site is left alone", any("other.org" in url for url in urls))
truthy("the fresh crawl is there", any("/fresh" in url for url in urls))
check("vectors stay aligned with chunks", len(after_vectors), len(after))

check("subdomains belong to the site", _store.same_site("https://admission.lpu.in/x", "lpu.in"), True)
check("www belongs to the site", _store.same_site("https://www.lpu.in/x", "lpu.in"), True)
check("a look-alike does not", _store.same_site("https://notlpu.in/x", "lpu.in"), False)
_store.clear()

# --------------------------------------------------------------------------
# Ranking must not discard the weakest passage that genuinely matched.
# --------------------------------------------------------------------------
SAME_TEXT = "Modern comfortable hostel facilities with all amenities included on campus"
TWO_URLS = [
    {"url": "https://www.lpu.in/international", "title": "Intl", "heading": "Accommodation",
     "content": SAME_TEXT, "passage": SAME_TEXT},
    {"url": "https://www.lpu.in/international/international-students.php", "title": "Intl",
     "heading": "Accommodation", "content": SAME_TEXT, "passage": SAME_TEXT},
    {"url": "https://www.lpu.in/student-services/residence.php", "title": "Residence",
     "heading": "Hostels", "content": "Safe secure supervised hostel living for students",
     "passage": "Safe secure supervised hostel living for students"},
]
paired, _ = rank(TWO_URLS, "hostel", None, None, limit=5)
check("the same text on two URLs is shown once", len(paired), 2)
check("both distinct pages survive",
      sorted(r["url"].split("/")[-1] for r in paired), ["international", "residence.php"])
check("a query matching nothing still returns nothing",
      rank(TWO_URLS, "quantum chromodynamics", None, None, 5)[0], [])

# --------------------------------------------------------------------------
# A partial match is still an answer.
#
# Handed five real passages about hostels, the model replied "I don't have any
# information about hostel fees" and told the student to go and check the
# college website - the very pages it had just been given. The tool now says
# what a non-empty result means.
# --------------------------------------------------------------------------
from app.agent.tools import SYSTEM_INSTRUCTION as _INSTRUCTION, TOOL_SPECS as _SPECS  # noqa: E402

knowledge_tool = next(
    spec for spec in _SPECS if spec["name"] == "search_college_knowledge"
)
truthy("the tool tells the model to read its guidance",
       "guidance" in knowledge_tool["description"])
truthy("and never to claim nothing when passages came back",
       "Never reply that you have no information when passages came back"
       in knowledge_tool["description"])
truthy("and not to deflect to the website it just read",
       "ARE the college website" in knowledge_tool["description"])

truthy("the prompt treats a partial match as an answer",
       "A partial match is still an answer" in _INSTRUCTION)
truthy("the prompt forbids the deflection",
       "never send the student off to read the college website" in _INSTRUCTION)

# --------------------------------------------------------------------------
# Chat memory: the window, the budget and the title.
# --------------------------------------------------------------------------
from app.chat.memory import HISTORY_PREAMBLE, derive_title  # noqa: E402

check("a title comes from the question",
      derive_title("What is my attendance in CSE329?"), "My attendance in CSE329")
# Every layer of politeness comes off, not just the first.
check("greeting and filler are both trimmed",
      derive_title("hey can you show me my timetable"), "My timetable")
check("a long question is cut", derive_title(" ".join(["word"] * 20)).endswith("…"), True)
check("an empty question still gets a title", derive_title(""), "New chat")

truthy("the history is labelled as history",
       "earlier in this same conversation" in HISTORY_PREAMBLE)
truthy("and old figures are marked as stale",
       "never repeat one as the current figure" in HISTORY_PREAMBLE)

# The models must actually accept the history, or none of this reaches them.
root = pathlib.Path(__file__).resolve().parents[1]
for name in ("gemini_service", "ollama_service"):
    source = (root / "app" / "agent" / f"{name}.py").read_text(encoding="utf-8")
    truthy(f"{name} accepts history", "history: list[dict[str, str]] | None" in source)
    truthy(f"{name} accepts the summary context", "context: str = \"\"" in source)
    truthy(f"{name} can summarise a thread", "def complete(" in source)

providers = (root / "app" / "agent" / "providers.py").read_text(encoding="utf-8")
truthy("the router loads the thread", "build_context" in providers)
truthy("the router saves the exchange", "record_exchange" in providers)
truthy("and compresses it once it is long", "summarise_older" in providers)

# The embedder must not read the chat base URL - that bug silently broke search.
embeddings = (root / "app" / "rag" / "embeddings.py").read_text(encoding="utf-8")
truthy("embeddings use their own base URL", "ollama_embedding_base_url" in embeddings)
check("embeddings never use the chat URL", "settings.ollama_base_url" in embeddings, False)

# The store must not depend on numpy to keep what was embedded.
store_source = (root / "app" / "rag" / "store.py").read_text(encoding="utf-8")
check("saving never calls numpy.save", "_np.save" in store_source, False)
truthy("vectors are written with the standard library", "flat.tobytes()" in store_source)

print(f"\n{PASSED} checks passed, {len(FAILED)} failed")
for failure in FAILED:
    print("  FAIL " + failure)
sys.exit(1 if FAILED else 0)
