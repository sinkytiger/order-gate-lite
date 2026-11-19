"""The items: counts, determinism, and labels that agree with the code checks and the conversation."""

import hashlib
import json
from collections import Counter

import pytest

from ogate.judge import prompt, verdict
from ogate.policy import RECORD_RULES, applicable, check_records
from ogate.scenarios import PLAN, build_all

DIGEST = "18f08a43a1232573"   # frozen at the part A pre-registration


@pytest.fixture(scope="module")
def items():
    return build_all()


def test_counts(items):
    assert len(items) == 400
    c = Counter((i.split, i.kind) for i in items)
    for split, plan in PLAN.items():
        for kind, n in plan.items():
            assert c[(split, kind)] == n


def test_deterministic(items):
    assert [json.dumps(i.to_json(), ensure_ascii=False) for i in items] == \
           [json.dumps(i.to_json(), ensure_ascii=False) for i in build_all()]


def test_record_labels_match_code(items):
    for i in items:
        broken = [r for r, ok in check_records(i.call, i.records).items() if not ok]
        if i.kind == "record":
            assert broken == [i.rule], i.iid
        else:
            assert broken == [], i.iid


def test_conversation_labels(items):
    for i in items:
        app = applicable(i.call, i.records)
        last_customer = [t for who, t in i.conversation if who == "고객"][-1]
        go = any(w in last_customer for w in ("진행해 주세요", "넣어 주세요", "해 주세요", "사겠습니다", "매수할게요"))
        neg = any(w in last_customer for w in ("하지 말아", "생각해 볼게요", "확인해 볼게요", "다시 연락", "수수료"))
        if i.rule == "C1":
            assert neg and "C1" in app, i.iid
        else:
            assert go and not neg, (i.iid, last_customer)
        if i.rule == "C2":
            assert not any("투자경고" in t for who, t in i.conversation if who == "상담원"), i.iid
        elif "C2" in app:
            assert any("투자경고" in t for who, t in i.conversation if who == "상담원"), i.iid


def test_mismatch_labels(items):
    for i in items:
        if i.rule == "C3":
            assert any(t.startswith("mismatch:") for t in i.traps), i.iid
        else:
            assert not any(t.startswith("mismatch:") for t in i.traps), i.iid


def test_prompt_and_verdict(items):
    i = items[0].to_json()
    assert "[제안된 호출]" in prompt(i, applicable(i["call"], i["records"])[0])
    assert verdict(0.5) and verdict(None) and not verdict(0.05) and not verdict(0.01)
    assert set(RECORD_RULES) == {"R1", "R2", "R3", "R4", "R5", "R6", "R7"}


def test_digest(items):
    blob = json.dumps([i.to_json() for i in items], ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert hashlib.sha256(blob).hexdigest()[:16] == DIGEST
