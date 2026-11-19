"""Command line.

    python -m ogate items                                   # write data/items.json
    python -m ogate judge --model qwen3:4b --split dev      # every applicable question for every item
    python -m ogate judge --model llama3.2:3b --split dev --rules C1,C2,C3
    python -m ogate report --split test
    python -m ogate agent --model claude-haiku-5-5 --split test --condition gate --runs 3   # part B
    python -m ogate agent-report --model claude-haiku-5-5 --split test

A judge run asks the model each applicable question once and saves P(yes) per rule; the gates are computed from
those saved answers and the code checks, so every gate sees the same judge answers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .judge import p_yes_ollama, prompt
from .policy import applicable
from .scenarios import build_all

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


def tag(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def judge_item(model: str, item: dict, rules: list[str] | None, ask=None) -> dict:
    """ask(prompt) -> answer dict; defaults to the local model through Ollama."""
    path = RUNS / tag(model) / f"{item['iid']}.json"
    rec = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"iid": item["iid"], "model": model,
                                                                             "answers": {}}
    todo = [r for r in applicable(item["call"], item["records"]) if (rules is None or r in rules)
            and r not in rec["answers"]]
    for r in todo:
        rec["answers"][r] = ask(prompt(item, r)) if ask else p_yes_ollama(model, prompt(item, r))
    if todo:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def run_agent(a) -> int:
    import random

    from .agent import JUDGE_CTX, ClaudeAgent, Gate, OllamaAgent, run_episode
    from .claude import Budget, ClaudeJudge, make_client
    from .judge import p_yes_ollama as ollama_ask
    from .tasks import build_tasks
    out = RUNS / "agent" / tag(a.model) / a.condition
    budget = Budget(RUNS)
    client = make_client() if (a.model.startswith("claude") or "claude" in (a.judge_model or "")) else None
    agent = ClaudeAgent(a.model, budget, client) if a.model.startswith("claude") else OllamaAgent(a.model)
    judge_model = a.judge_model or ("qwen3:4b" if a.condition == "gate_qwen" else "claude-haiku-5-5")
    if judge_model.startswith("claude"):
        ask = ClaudeJudge(judge_model, budget, client or make_client()).p_yes
    else:
        def ask(text):
            return ollama_ask(judge_model, text, num_ctx=JUDGE_CTX)
    for seed in range(a.runs):
        for t in build_tasks(a.split):
            if a.only and a.only not in t.tid:
                continue
            path = out / f"{t.tid}_s{seed}.json"
            if path.exists():
                continue
            gate = Gate(a.condition, judge_model, a.judge_rules.split(","), a.flag_rate,
                        random.Random(f"random-gate:{t.tid}:{seed}"), ask=ask)
            ep = run_episode(t, agent, gate, seed)
            ep.update({"model": a.model, "split": a.split, "judge_model": judge_model,
                       "judge_rules": a.judge_rules, "flag_rate": a.flag_rate})
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(ep, ensure_ascii=False, indent=1), encoding="utf-8")
            flags = sum(p.get("flag", False) for p in ep["proposals"])
            print(f"[{a.model} {a.condition} s{seed}] {t.tid}: {'PASS' if ep['passed'] else 'fail'} end={ep['end']} "
                  f"steps={len(ep['steps'])} proposals={len(ep['proposals'])} flags={flags} {ep['fail_reasons']}",
                  flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ogate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("items")
    j = sub.add_parser("judge")
    j.add_argument("--model", required=True)
    j.add_argument("--split", default="dev", choices=["dev", "test"])
    j.add_argument("--rules")
    r = sub.add_parser("report")
    r.add_argument("--split", default="test", choices=["dev", "test"])
    r.add_argument("--out")
    g = sub.add_parser("agent")
    g.add_argument("--model", required=True)
    g.add_argument("--split", default="dev", choices=["dev", "test"])
    g.add_argument("--condition", required=True, choices=["none", "gate", "gate_qwen", "placebo", "random"])
    g.add_argument("--runs", type=int, default=1)
    g.add_argument("--judge-model", help="default: claude-haiku-5-5 for gate, qwen3:4b for gate_qwen")
    g.add_argument("--judge-rules", default="C1,C2")
    g.add_argument("--flag-rate", type=float, default=0.0)
    g.add_argument("--only")
    gr = sub.add_parser("agent-report")
    gr.add_argument("--model", required=True)
    gr.add_argument("--split", default="test", choices=["dev", "test"])
    gr.add_argument("--out")
    sub.add_parser("export")
    a = ap.parse_args(argv)
    if a.cmd == "agent":
        return run_agent(a)
    if a.cmd == "export":
        from .export import export
        for p in export(RUNS, ROOT / "reports"):
            print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size:,} bytes)")
        return 0
    if a.cmd == "agent-report":
        from .agent_report import agent_report, exploratory_b, prereg_b
        text = agent_report(RUNS / "agent" / tag(a.model), a.split)
        if a.split == "test":
            text += "\n" + prereg_b(RUNS / "agent" / tag(a.model), a.split)
            text += "\n" + exploratory_b(RUNS / "agent" / tag(a.model), a.split)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")
        print(text)
        return 0
    items = [i.to_json() for i in build_all()]
    if a.cmd == "items":
        out = ROOT / "data" / "items.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {len(items)} items to {out}")
        return 0
    if a.cmd == "report":
        from .report import prereg, report
        sel = [i for i in items if i["split"] == a.split]
        text = report(RUNS, sel) + "\n" + prereg(RUNS, sel)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")
        print(text)
        return 0
    rules = a.rules.split(",") if a.rules else None
    ask = None
    if a.model.startswith("claude"):
        from .claude import Budget, ClaudeJudge
        ask = ClaudeJudge(a.model, Budget(RUNS)).p_yes
    for it in items:
        if it["split"] != a.split:
            continue
        rec = judge_item(a.model, it, rules, ask)
        ans = " ".join(f"{k}={v['p_yes']:.3f}" if v["p_yes"] is not None else f"{k}=?" for k, v in rec["answers"].items())
        print(f"[{a.model}] {it['iid']} {it['rule'] or 'ok'}: {ans}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
