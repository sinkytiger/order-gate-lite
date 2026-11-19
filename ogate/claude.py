"""Claude through the official SDK, with one spending cap shared by every paid call (agent and judge).

Prices are $ per million tokens (Claude API pricing page, checked 2026-11-11 for fin-formulate-lite): Haiku 5.5
$0.10 in / $0.50 out for prompts up to 100,000 tokens, cache reads 0.1x and 5-minute cache writes 1.25x the input
price. Every request is refused once the spend recorded in the saved runs (archived ones included) plus this
process's spend reaches BUDGET.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

PRICES = {"claude-haiku-5-5": (0.10, 0.50)}
BUDGET = float(os.environ.get("OGATE_BUDGET", "3.0"))   # dollars; approved by the user on 2026-11-19


class BudgetExceeded(RuntimeError):
    pass


def cost_of(model: str, u: dict) -> float:
    if model not in PRICES:
        return 0.0
    pin, pout = PRICES[model]
    return (u.get("input_tokens", 0) * pin + u.get("cache_creation_input_tokens", 0) * pin * 1.25
            + u.get("cache_read_input_tokens", 0) * pin * 0.1 + u.get("output_tokens", 0) * pout) / 1e6


def _walk(o, model: str, acc: list) -> None:
    """Every 'usage' dict in a saved record, priced with the nearest enclosing 'model'."""
    if isinstance(o, dict):
        if isinstance(o.get("model"), str):
            model = o["model"]
        if isinstance(o.get("usage"), dict):
            acc.append(cost_of(model, o["usage"]))
        for k, v in o.items():
            if k != "usage":
                _walk(v, model, acc)
    elif isinstance(o, list):
        for v in o:
            _walk(v, model, acc)


def spent(root: Path) -> float:
    acc: list = []
    for f in root.rglob("*.json"):
        try:
            _walk(json.loads(f.read_text(encoding="utf-8")), "", acc)
        except (OSError, ValueError):
            continue
    return sum(acc)


class Budget:
    def __init__(self, root: Path):
        self.base, self.session = spent(root), 0.0

    def check(self) -> None:
        if self.base + self.session >= BUDGET:
            raise BudgetExceeded(f"spend ${self.base + self.session:.4f} reached the ${BUDGET} budget")

    def charge(self, model: str, u: dict) -> None:
        self.session += cost_of(model, u)


def make_client():
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY") or \
        (Path.home() / ".harnessforge" / "anthropic_api_key.txt").read_text(encoding="utf-8").strip()
    return anthropic.Anthropic(api_key=key, max_retries=4, timeout=120)


def usage_of(r) -> dict:
    return {"input_tokens": r.usage.input_tokens or 0, "output_tokens": r.usage.output_tokens or 0,
            "cache_creation_input_tokens": r.usage.cache_creation_input_tokens or 0,
            "cache_read_input_tokens": r.usage.cache_read_input_tokens or 0}


ANSWER_FORMAT = {"type": "json_schema", "schema": {
    "type": "object", "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}}, "required": ["answer"],
    "additionalProperties": False}}


class ClaudeJudge:
    """A Claude model as the yes/no judge, on the same prompt as the local judges. As with them, the reply is
    constrained to {"answer": "yes" | "no"} (structured outputs), so the judge answers without writing out any
    reasoning first. The API returns no token probabilities, so P(yes) is 1.0 for a "yes" reply and 0.0 for a "no"
    (the 0.05 threshold then means "the reply was no"); an unreadable reply is None, which counts as "yes". Thinking
    off, default sampling, one draw."""

    def __init__(self, model: str, budget: Budget, client=None):
        self.model, self.budget = model, budget
        self.client = client or make_client()

    def p_yes(self, text: str) -> dict:
        self.budget.check()
        t = time.time()
        r = self.client.messages.create(model=self.model, max_tokens=64, thinking={"type": "disabled"},
                                        output_config={"format": ANSWER_FORMAT},
                                        messages=[{"role": "user", "content": text}])
        u = usage_of(r)
        self.budget.charge(self.model, u)
        reply = "".join(b.text for b in r.content if b.type == "text").strip()
        low = reply.lower()
        m = re.search(r'"answer"\s*:\s*"(yes|no)"', low) or re.match(r'\W*(yes|no)\b', low)
        p = None if m is None else (1.0 if m.group(1) == "yes" else 0.0)
        return {"p_yes": p, "reply": reply, "prompt_tokens": u["input_tokens"], "seconds": round(time.time() - t, 2),
                "model": self.model, "usage": u}
