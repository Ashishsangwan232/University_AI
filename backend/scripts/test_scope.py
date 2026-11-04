"""Tests for the LPU/academics-only scope check. No network, no model.

    python scripts/test_scope.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.agent.scope import is_off_topic  # noqa: E402
from app.agent.tools import SYSTEM_INSTRUCTION  # noqa: E402

BLOCKED = [
    "suggest me a good movie to watch",
    "tell me a joke",
    "who won the cricket match yesterday",
    "what is the bitcoin price today",
    "give me a biryani recipe",
    "how do I impress my crush",
    "write a love letter for my girlfriend",
    "best phone under 20000",
    "koi accha gaana sunao",
    "what is my horoscope for today",
    "who will win the elections",
    "how to get better at valorant",
    "lyrics of a song",
]

ALLOWED = [
    "what is my attendance",
    "hi",
    "thanks",
    "what are LPU hostel fees",
    "explain binary search",
    "what is cryptography",
    "solve x^2 - 4 = 0",
    "how do I prepare for my exam",
    "what is my timetable tomorrow",
    "is there a cricket ground on campus",
    "LPU placement stats",
    "bhai mera attendance kitna hai",
    "help me with my assignment on operating systems",
    "what about tomorrow?",
]

failed = []
for q in BLOCKED:
    if not is_off_topic(q):
        failed.append(f"should block: {q!r}")
for q in ALLOWED:
    if is_off_topic(q):
        failed.append(f"should allow: {q!r}")
if "STRICT SCOPE" not in SYSTEM_INSTRUCTION:
    failed.append("system instruction is missing the scope rule")

total = len(BLOCKED) + len(ALLOWED) + 1
print(f"{total - len(failed)}/{total} passed")
for f in failed:
    print("FAIL", f)
sys.exit(1 if failed else 0)
