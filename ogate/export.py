"""Writes the test results as flat files under reports/ (runs/ is not in git).

    reports/partA_answers_test.csv      one row per judge answer: item, kind, broken rule, judge, question, P(yes)
    reports/partB_episodes_test.csv     one row per agent episode: condition, task, run, outcome, send-backs, cost
    reports/partB_conversations_test.jsonl   one line per episode: the customer-agent conversation, the proposed
                                        write calls with the gate's answers, the executed calls, the customer's log
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .claude import _walk
from .scenarios import build_all
from .tasks import build_tasks

JUDGES = {"qwen3:4b": "qwen3_4b", "llama3.2:3b": "llama3.2_3b", "claude-haiku-5-5": "claude-haiku-5-5"}
CONDITIONS = ("none", "gate", "gate_qwen", "placebo", "random")


def export(runs: Path, out: Path, agent_model: str = "claude-haiku-5-5", split: str = "test") -> list[Path]:
    out.mkdir(exist_ok=True)
    a_path = out / f"partA_answers_{split}.csv"
    n = 0
    with a_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["iid", "kind", "broken_rule", "judge", "question", "p_yes"])
        for it in build_all():
            if it.split != split:
                continue
            for judge, folder in JUDGES.items():
                f = runs / folder / f"{it.iid}.json"
                if not f.exists():
                    raise FileNotFoundError(f)
                for rule, v in json.loads(f.read_text(encoding="utf-8"))["answers"].items():
                    w.writerow([it.iid, it.kind, it.rule or "", judge, rule, "" if v["p_yes"] is None else v["p_yes"]])
                    n += 1
    if n == 0:
        raise RuntimeError("no part A answers exported")
    b_path = out / f"partB_episodes_{split}.csv"
    c_path = out / f"partB_conversations_{split}.jsonl"
    tasks = build_tasks(split)
    rows = 0
    with b_path.open("w", encoding="utf-8", newline="") as fb, c_path.open("w", encoding="utf-8") as fc:
        w = csv.writer(fb)
        w.writerow(["condition", "tid", "type", "run", "passed", "fail_reasons", "end", "agent_steps", "write_proposals",
                    "sent_back", "sent_back_checks", "executed_calls", "violating_executions", "cost_usd"])
        for cond in CONDITIONS:
            for t in tasks:
                for seed in range(3):
                    f = runs / "agent" / agent_model / cond / f"{t.tid}_s{seed}.json"
                    if not f.exists():
                        raise FileNotFoundError(f)
                    e = json.loads(f.read_text(encoding="utf-8"))
                    acc: list = []
                    _walk(e, "", acc)
                    props = [p for p in e["proposals"] if "call" in p]
                    sent = [p for p in props if p["flag"]]
                    w.writerow([cond, t.tid, t.ttype, seed, int(e["passed"]), "; ".join(e["fail_reasons"]), e["end"],
                                len(e["steps"]), len(props), len(sent),
                                "; ".join("+".join(p["failed"]) or "generic" for p in sent),
                                json.dumps([x["call"] for x in e["executed"]], ensure_ascii=False),
                                e["violating_executions"], round(sum(acc), 6)])
                    fc.write(json.dumps({"condition": cond, "tid": t.tid, "type": t.ttype, "run": seed,
                                         "passed": e["passed"], "conversation": e["conversation"],
                                         "proposals": e["proposals"], "executed": e["executed"],
                                         "customer_log": e["customer_log"]}, ensure_ascii=False) + "\n")
                    rows += 1
    if rows != len(CONDITIONS) * len(tasks) * 3:
        raise RuntimeError(f"expected {len(CONDITIONS) * len(tasks) * 3} episodes, wrote {rows}")
    return [a_path, b_path, c_path]
