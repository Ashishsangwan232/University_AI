"""Checks that every model gets the LPU-only scope rule. No network, no model.

Whether a question is in scope is decided by the model, so this only checks
the rule is in place. To see real refusals, ask the running app.

    python scripts/test_scope.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.agent.scope import REFUSAL, SCOPE_REMINDER, SCOPE_RULE  # noqa: E402
from app.agent.tools import SYSTEM_INSTRUCTION  # noqa: E402

failed = []
if not SYSTEM_INSTRUCTION.startswith("You are CampusAI") or SCOPE_RULE not in SYSTEM_INSTRUCTION[:3000]:
    failed.append("scope rule is not at the start of the system instruction")
if not SYSTEM_INSTRUCTION.endswith(SCOPE_REMINDER):
    failed.append("scope reminder is not at the end of the system instruction")
if REFUSAL not in SCOPE_RULE:
    failed.append("scope rule does not carry the refusal text")

print(f"{3 - len(failed)}/3 passed")
for f in failed:
    print("FAIL", f)
sys.exit(1 if failed else 0)
