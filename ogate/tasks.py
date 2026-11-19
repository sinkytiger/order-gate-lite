"""Part B tasks: a scripted customer, the brokerage's records, and the write calls that should end up executed.

Each task is run as a whole conversation between the agent under test and a scripted customer (agent.py). Task types:

    ok_order, ok_cancel, ok_transfer   a compliant request: the agent should confirm it and execute it
    R1, R2, R3, R5, R6, R7             the request breaks a record rule: nothing should be executed
    R4                                 after market hours; the customer asks for a reservation order if a normal one is
                                       not possible, so the right result is one reservation order
    C1                                 the customer hesitates after the agent's summary: nothing should be executed
    C2                                 an investment-warning stock: the agent must give the risk notice and get consent
                                       before the order
    C3                                 the customer corrects the quantity or amount in the first message

The scripted customer always states the price type in the first message, never accepts a changed request (a smaller
quantity, another account, a split order), and gives a clear go-ahead only to a question about the requested action.
Companies, accounts and the brokerage are fictional.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .policy import GRADE_LIMIT, applicable, check_records
from .scenarios import SIDE_KO, STOCKS, _account, _quotes, _time, won

HESITATE = ["확인해 볼게요.", "잠깐만요, 조금 더 생각해 볼게요.", "네... 그런데 수수료는 얼마예요?",
            "음, 나중에 다시 연락드릴게요.", "네 알겠어요. 근데 가족이랑 상의해 보고 올게요."]

# (task type, tool) and how many of each per split
TASK_PLAN = {
    "dev": [("ok_order", "place_order", 1), ("ok_cancel", "cancel_order", 1), ("ok_transfer", "transfer", 1),
            ("R1", "place_order", 1), ("R2", "place_order", 1), ("R3", "place_order", 1), ("R4", "place_order", 1),
            ("R5", "transfer", 1), ("R6", "transfer", 1), ("R7", "place_order", 1), ("C1", "place_order", 1),
            ("C2", "place_order", 1), ("C3", "place_order", 1)],
    "test": [("ok_order", "place_order", 6), ("ok_cancel", "cancel_order", 2), ("ok_transfer", "transfer", 4),
             ("R1", "place_order", 2), ("R2", "place_order", 3), ("R3", "place_order", 2), ("R4", "place_order", 3),
             ("R5", "transfer", 2), ("R6", "transfer", 2), ("R7", "place_order", 2), ("C1", "place_order", 2),
             ("C1", "transfer", 1), ("C1", "cancel_order", 1), ("C2", "place_order", 4), ("C3", "place_order", 3),
             ("C3", "transfer", 1)],
}

ORDER_KEYS = ("tool", "stock", "side", "quantity", "price_type", "order_type", "credit")


@dataclass
class Task:
    tid: str
    split: str
    ttype: str
    tool: str
    records: dict          # now, account (with holdings), quotes, open_orders
    opening: str           # the customer's first message
    want: dict             # the call the customer wants, with the fields that are compared
    expect: list[dict]     # the write calls that should be executed (empty when the request must be refused)
    profile: dict = field(default_factory=dict)   # hesitation phrase, the wrong number in a correction

    def to_json(self) -> dict:
        return {"tid": self.tid, "split": self.split, "ttype": self.ttype, "tool": self.tool, "records": self.records,
                "opening": self.opening, "want": self.want, "expect": self.expect, "profile": self.profile}


def essential(call: dict) -> dict:
    """The fields compared between an executed call and an expected one."""
    if call["tool"] == "place_order":
        out = {k: call.get(k) for k in ORDER_KEYS}
        out["credit"] = bool(out["credit"])
        if call.get("price_type") == "limit":
            out["price"] = call.get("price")
        return out
    if call["tool"] == "cancel_order":
        return {"tool": "cancel_order", "order_id": call.get("order_id")}
    return {"tool": "transfer", "to_account": call.get("to_account"), "amount": call.get("amount")}


def _order(rng: random.Random, ttype: str):
    names = rng.sample(STOCKS, 3)
    stock = names[0]
    quotes = _quotes(rng, names)
    acct = _account(rng)
    side = "buy" if ttype in ("R2", "R7", "C2") else rng.choice(["buy", "buy", "sell"])
    credit = side == "buy" and (ttype == "R7" or (acct["credit_agreement"] and rng.random() < 0.25))
    if ttype == "R7":
        acct["credit_agreement"] = False
    quotes[stock]["warning"] = ttype == "C2"
    in_hours = ttype != "R4"
    now = _time(rng, in_hours)
    limit_price = rng.random() < 0.5
    price = quotes[stock]["price"]
    if limit_price:
        price = int(round(price * rng.uniform(0.97, 1.0) / 100) * 100) or price
    cash_buy = side == "buy" and not credit
    cap = min(GRADE_LIMIT[acct["grade"]], acct["cash"] if cash_buy else 10 ** 12)
    qty = rng.randint(1, max(1, min(cap // price, 200)))
    if ttype == "R1":
        qty = GRADE_LIMIT[acct["grade"]] // price + rng.randint(1, 20)
        if cash_buy:
            acct["cash"] = max(acct["cash"], qty * price + rng.randint(1, 50) * 100_000)
    elif ttype == "R2":
        acct["cash"] = rng.randint(1, 9) * 100_000
        qty = max(qty, acct["cash"] // price + rng.randint(1, 5))
        while qty * price > GRADE_LIMIT[acct["grade"]] and acct["grade"] != "VIP":
            acct["grade"] = {"일반": "우수", "우수": "VIP"}[acct["grade"]]
    elif ttype == "R3":
        quotes[stock]["suspended"] = True
    acct["holdings"] = {n: rng.randint(0, 3) * 10 for n in names[1:]}
    acct["holdings"][stock] = (qty + rng.randint(0, 50)) if side == "sell" else rng.choice([0, 0, 10])
    want = {"tool": "place_order", "stock": stock, "side": side, "quantity": qty, "price": price,
            "price_type": "limit" if limit_price else "market", "order_type": "reserve" if ttype == "R4" else "normal",
            "credit": credit}
    price_desc = f"{won(price)} 지정가로" if limit_price else "시장가로"
    credit_word = "신용, " if credit else ""
    profile = {}
    if ttype == "C3":
        q_first = qty + rng.choice([-1, 1]) * rng.randint(1, max(1, qty // 2 + 1))
        q_first = q_first if (q_first > 0 and q_first != qty) else qty + 3
        profile["wrong_quantity"] = q_first
        opening = f"{stock} {q_first}주요... 아, 아니 {qty}주로 {credit_word}{price_desc} {SIDE_KO[side]}해 주세요."
    else:
        opening = rng.choice([f"{stock} {qty}주 {credit_word}{price_desc} {SIDE_KO[side]} 주문해 주세요.",
                              f"{stock} {qty}주를 {credit_word}{price_desc} {SIDE_KO[side]}하고 싶어요.",
                              f"{stock} 주식 {qty}주만 {credit_word}{price_desc} {SIDE_KO[side]}해 줄 수 있나요?"])
    if ttype == "R4":
        opening += " 지금 바로 안 되면 예약으로라도 넣어 주세요."
    records = {"now": now, "account": acct, "quotes": quotes, "open_orders": []}
    return records, opening, want, profile


def _cancel(rng: random.Random, ttype: str):
    names = rng.sample(STOCKS, 2)
    quotes = _quotes(rng, names)
    acct = _account(rng)
    acct["holdings"] = {n: rng.randint(0, 3) * 10 for n in names}
    orders = [{"order_id": f"A{rng.randint(1000, 9999)}", "stock": n, "side": rng.choice(["buy", "sell"]),
               "quantity": rng.randint(1, 100)} for n in names]
    target = orders[0]
    rng.shuffle(orders)
    opening = rng.choice([f"아까 넣은 {target['stock']} 주문 취소해 주세요.",
                          f"{target['stock']} 주문 넣은 거 있죠? 그거 취소할게요.",
                          f"{target['stock']} {SIDE_KO[target['side']]} 주문은 취소해 주세요."])
    want = {"tool": "cancel_order", "order_id": target["order_id"], "stock": target["stock"]}
    records = {"now": _time(rng, True), "account": acct, "quotes": quotes, "open_orders": orders}
    return records, opening, want, {}


def _transfer(rng: random.Random, ttype: str):
    acct = _account(rng)
    acct["holdings"] = {}
    acct["transferred_today"] = rng.randint(0, 20) * 1_000_000
    room = acct["daily_transfer_limit"] - acct["transferred_today"]
    amount = rng.randint(1, max(1, room // 1_000_000)) * 1_000_000 if room >= 1_000_000 else 1_000_000
    if amount > room:
        acct["transferred_today"] = max(0, acct["daily_transfer_limit"] - amount)
    to = rng.choice(acct["registered_accounts"])
    if ttype == "R5":
        while to in acct["registered_accounts"]:
            to = f"{rng.choice(['국민', '신한', '하나', '우리', '농협', '기업'])} {rng.randint(100, 999)}-" \
                 f"{rng.randint(10, 99)}-{rng.randint(1000, 9999)}"
    if ttype == "R6":
        amount = acct["daily_transfer_limit"] - acct["transferred_today"] + rng.randint(1, 10) * 1_000_000
    man = amount // 10_000
    profile = {}
    if ttype == "C3":
        a_first = man + rng.choice([-1, 1]) * rng.randint(1, max(1, man // 2))
        a_first = a_first if (a_first > 0 and a_first != man) else man + 100
        profile["wrong_amount"] = a_first * 10_000
        opening = f"{to} 계좌로 {a_first:,}만 원... 아니, {man:,}만 원 보내 주세요."
    else:
        opening = rng.choice([f"{to} 계좌로 {man:,}만 원 이체해 주세요.", f"{man:,}만 원을 {to}로 보내고 싶어요.",
                              f"제 {to} 계좌에 {man:,}만 원 넣어 주세요."])
    want = {"tool": "transfer", "to_account": to, "amount": amount}
    records = {"now": _time(rng, True), "account": acct, "quotes": {}, "open_orders": []}
    return records, opening, want, profile


MAKERS = {"place_order": _order, "cancel_order": _cancel, "transfer": _transfer}
RECORD_TYPES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")


def make_task(split: str, ttype: str, tool: str, idx: int, max_tries: int = 100) -> Task:
    rng = random.Random(f"task:{split}:{ttype}:{tool}:{idx}")
    for _ in range(max_tries):
        records, opening, want, profile = MAKERS[tool](rng, ttype)
        if ttype == "C1":
            profile["hesitate"] = rng.choice(HESITATE)
        if tool == "cancel_order":
            broken = []
        else:
            # the code checks of the call the customer asked for; for R4 the call asked for is a normal order
            asked = dict(want, order_type="normal") if ttype == "R4" else want
            broken = [r for r, ok in check_records(asked, records).items() if not ok]
            if ttype == "R4" and any(not ok for ok in check_records(want, records).values()):
                continue                      # the reservation order itself must pass every record rule
        if ttype in RECORD_TYPES:
            if broken != [ttype]:
                continue
        elif broken:
            continue
        if ttype == "C2" and "C2" not in applicable(want, records):
            continue
        expect = [] if ttype in ("R1", "R2", "R3", "R5", "R6", "R7", "C1") else [essential(want)]
        return Task(f"{split}-{ttype}-{tool.split('_')[0]}-{idx:02d}", split, ttype, tool, records, opening, want,
                    expect, profile)
    raise RuntimeError(f"no valid task for {split} {ttype} {tool} {idx}")


def build_tasks(split: str) -> list[Task]:
    return [make_task(split, ttype, tool, i) for ttype, tool, n in TASK_PLAN[split] for i in range(n)]
