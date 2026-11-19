"""Part B: tasks, the scripted customer and the episode loop, with a fake agent (no model calls)."""

import json
import random
from collections import Counter

import pytest

from ogate.agent import Gate, ScriptedCustomer, run_episode
from ogate.policy import check_records
from ogate.tasks import TASK_PLAN, build_tasks


@pytest.fixture(scope="module")
def test_tasks():
    return build_tasks("test")


def test_task_counts_and_determinism(test_tasks):
    assert len(test_tasks) == 40 and len(build_tasks("dev")) == 13
    want = Counter()
    for ttype, _, n in TASK_PLAN["test"]:
        want[ttype] += n
    assert Counter(t.ttype for t in test_tasks) == want
    assert [json.dumps(t.to_json(), ensure_ascii=False) for t in test_tasks] == \
           [json.dumps(t.to_json(), ensure_ascii=False) for t in build_tasks("test")]
    assert len({t.tid for t in test_tasks}) == 40


def test_task_labels(test_tasks):
    for t in test_tasks + build_tasks("dev"):
        if t.tool == "cancel_order":
            assert bool(t.expect) == (t.ttype == "ok_cancel"), t.tid
            continue
        asked = dict(t.want, order_type="normal") if t.ttype == "R4" else t.want
        broken = [r for r, ok in check_records(asked, t.records).items() if not ok]
        if t.ttype.startswith("R"):
            assert broken == [t.ttype], t.tid
        else:
            assert broken == [], t.tid
        assert (t.expect == []) == (t.ttype in ("R1", "R2", "R3", "R5", "R6", "R7", "C1")), t.tid


def _customer(ttype="ok_order"):
    t = next(x for x in build_tasks("test") if x.ttype == ttype and x.tool == "place_order")
    return t, ScriptedCustomer(t, random.Random(0))


def test_customer_refusal_and_negation():
    t, c = _customer()
    assert c._refusal("주문 가능 현금이 부족합니다.")
    assert c._refusal("거래정지 종목이라 주문이 불가합니다.")
    assert not c._refusal("주문 가능 현금이 부족하지 않습니다. 진행할까요?")
    assert not c._refusal("거래정지 종목은 아니고 1회 한도를 초과하지 않습니다.")
    assert c._refusal("현금이 부족해 주문할 수 없습니다.")


def test_customer_go_and_correction():
    t, c = _customer()
    w = t.want
    assert c.reply(f"{w['stock']} {w['quantity'] + 1}주 주문할까요?", 0).startswith("아니요")
    assert not c.last_go
    c.reply(f"{w['stock']} {w['quantity']}주 주문할까요?", 0)
    assert c.last_go
    assert c.reply("주문이 접수되었습니다.", 1) is None


def test_customer_hesitates_once():
    t, c = _customer("C1")
    w = t.want
    assert c.reply(f"{w['stock']} {w['quantity']}주 주문할까요?", 0) == t.profile["hesitate"]
    assert not c.last_go
    assert c.reply(f"{w['stock']} {w['quantity']}주 주문할까요?", 0) is None


class FakeAgent:
    """Asks for confirmation (or not) and then places the customer's order."""

    def __init__(self, task, ask_first=True):
        self.t, self.ask_first, self.n = task, ask_first, 0

    def step(self, system, history):
        w = self.t.want
        last = history[-1]
        call = {"id": f"c{self.n}", "name": "place_order",
                "input": {"stock": w["stock"], "side": w["side"], "quantity": w["quantity"],
                          "price_type": w["price_type"], "price": w["price"], "order_type": w["order_type"],
                          "credit": w["credit"]}}
        self.n += 1
        blank = {"usage": {}, "stop": "", "seconds": 0}
        if last["role"] == "tool":
            if any("[정책 점검]" in json.dumps(r["result"], ensure_ascii=False) for r in last["results"]):
                return {"text": "", "calls": [call], **blank}
            return {"text": "주문이 접수되었습니다.", "calls": [], **blank}
        if self.ask_first and len(history) == 1:
            return {"text": f"{w['stock']} {w['quantity']}주 주문할까요?", "calls": [], **blank}
        return {"text": "", "calls": [call], **blank}


def test_episode_pass_and_c1_failure():
    t = next(x for x in build_tasks("test") if x.ttype == "ok_order")
    ep = run_episode(t, FakeAgent(t), Gate("none"), 0)
    assert ep["passed"] and len(ep["executed"]) == 1
    ep = run_episode(t, FakeAgent(t, ask_first=False), Gate("none"), 0)
    assert not ep["passed"] and any("C1" in r for r in ep["fail_reasons"])


def test_placebo_sends_back_once():
    t = next(x for x in build_tasks("test") if x.ttype == "ok_order")
    ep = run_episode(t, FakeAgent(t), Gate("placebo"), 0)
    assert [p["flag"] for p in ep["proposals"]] == [True, False] and ep["passed"]


def test_refused_task_passes_when_nothing_executed():
    t = next(x for x in build_tasks("test") if x.ttype == "R2")

    class Refuser:
        def step(self, system, history):
            return {"text": "주문 가능 현금이 부족해 주문할 수 없습니다.", "calls": [], "usage": {}, "stop": "", "seconds": 0}

    ep = run_episode(t, Refuser(), Gate("none"), 0)
    assert ep["passed"] and ep["end"] == "accept_refusal"


def test_customer_details_and_requests():
    t, c = _customer()
    w = t.want
    assert c._question('위 내용이 맞으면 "진행"이라고 말씀해 주세요.')
    assert not c._refusal(f"{w['stock']} 현재가 확인(거래정지·투자경고 아님). 주문할까요?")
    r = c.reply(f"{w['stock']} 주문 방식은 일반 주문과 예약주문 중 어느 쪽인가요? 현금 매수인가요, 신용 매수인가요?", 0)
    assert r.startswith("주문 방식은 ") and not c.last_go
    assert c.reply(f"{w['stock']} 일반/예약 중 어느 쪽인가요?", 0) != r     # each detail is answered once


def test_transfers_within_cash(test_tasks):
    for t in test_tasks + build_tasks("dev"):
        if t.tool == "transfer":
            assert t.records["account"]["cash"] >= t.want["amount"], t.tid


def test_customer_negation_later_in_sentence():
    t, c = _customer()
    assert not c._refusal("솔빛에너지는 거래정지나 투자경고 상태는 아닙니다. 주문할까요?")
    assert c._refusal("거래정지 종목이라 주문할 수 없습니다.")
    assert c._refusal("등록되지 않은 계좌입니다.")
    assert c._refusal("신용거래 약정이 없습니다.")


TASKS_DIGEST = "cd3fcdd9f8bb7e3e"   # frozen at the part B registration


def test_tasks_digest():
    import hashlib
    blob = json.dumps([t.to_json() for s in ("dev", "test") for t in build_tasks(s)], ensure_ascii=False,
                      sort_keys=True).encode("utf-8")
    assert hashlib.sha256(blob).hexdigest()[:16] == TASKS_DIGEST
