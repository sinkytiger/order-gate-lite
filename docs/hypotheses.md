# Pre-registered hypotheses

Registered in two commits, each before the runs it covers touched the test split. Part A (single calls, local
judges) is registered first: the item generator (`ogate/scenarios.py`, digest `18f08a43a1232573`), the judge prompt
and questions, the threshold, the gates, the scoring and the part A sections of this file are frozen at that
commit. The second commit, made after the part A test results of the local judges were known and before any
Claude judge or agent call on the test split, registers part B (the agent tasks, digest `cd3fcdd9f8bb7e3e`, the
scripted customer and hypotheses B1 to B4) and adds Claude Haiku 5.5 as a third judge in part A (gates G6 to G8,
hypotheses H5 to H8). The user asked on 2026-11-19 for a stronger model than the small local ones; the judge was
chosen over the agent because Haiku 5.5 already passed 12 of 13 dev tasks as the agent. Later changes are listed
at the end with a reason.

## The paper and what is tested here

JevAct ("Think Before You Act: Decision Gate for LLM Agents", [arXiv:2610.38620](https://arxiv.org/abs/2610.38620),
v1 of 2026-10-28) puts a gate in front of a tool-using agent's write calls and hand-offs. Before a write is executed,
compiled code checks the facts that can be read from the tool state, and a prefill-only decision model (Kev) answers
yes/no questions about the conversation; an answer counts as "no" only when P(yes) <= 0.05. A call that fails a
check is sent back to the agent with feedback; the write gate has a revision budget R = 2, and once it is used up
the next proposal is committed without another check. The paper reports that on τ²-bench Telecom all eight agents
improved, with pass^3 up 16.9 points on average; that flagging every write call once without checking it gave no
improvement over the base agent (50.0%); that an unconditional re-check left GPT-4.1's pass^3 at 26.0% to 28.0%
against 40.0% with the gate, while for gpt-oss-120b a re-check or random flags at the gate's rate raised pass^3 as
much as the full gate (32.0% to 42.0%); that questions needing arithmetic or date comparisons are what Kev answers
worst; and that 42 of the 101 incorrect write calls in its failure analysis broke no compiled question.

This study asks two things on a small Korean brokerage setting: (A) how well a code-plus-small-local-judge gate
separates violating write calls from compliant ones, and whether arithmetic belongs in code; (B) whether the gate
raises an agent's task success (pass^3) more than a placebo or random sending-back does. It is not a replication:
the judge here is a general local model (qwen3:4b), not Kev, and the policy, tools and conversations are synthetic.

## Setup

* **Policy** (`ogate/policy.py`): a fictional brokerage with seven record rules checked by code (R1 per-order limit
  by account grade, R2 cash, R3 trading suspension, R4 market hours or a reservation order, R5 registered receiving
  account, R6 daily transfer limit, R7 credit agreement) and three conversation questions for the judge (C1 a clear
  go-ahead after the agent's last summary, C2 the risk notice and consent before buying an investment-warning stock,
  C3 the call matches the customer's last request).
* **Judge** (`ogate/judge.py`): qwen3:4b through Ollama 0.40.16 (thinking off, temperature 0, seed 7, 4,096-token
  context), with the reply constrained to `{"answer": "yes" | "no"}` by a JSON schema. P(yes) is read from the
  top-10 log-probabilities at the position where the answer token is chosen, normalised over "yes" and "no"; a
  question counts as "no" only when P(yes) <= 0.05, as in the paper, and an unreadable answer counts as "yes".
  The prompt shows the Korean conversation, the tool records and the proposed call, and asks one question in
  English. llama3.2:3b is the second judge. Claude Haiku 5.5 is the third (`ogate/claude.py`): the same prompt,
  thinking off, default sampling (one draw, not repeatable), the reply constrained to the same answer schema by
  structured outputs. The API gives no token probabilities, so P(yes) is 1 for "yes" and 0 for "no"; the 0.05
  threshold then means "the reply was no".

### Part A: single calls

* **Items** (`ogate/scenarios.py`): a Korean conversation ending with a proposed write call (place_order,
  cancel_order or transfer), the tool records the agent has seen, and a label: compliant, or exactly one violated
  rule of three kinds: a record rule, a conversation question (C1, C2), or a mismatch with the request (C3).
  Conversations carry planted confusers (a correction, hesitation that sounds like assent, a chat that is not a
  risk notice). Dev split: 50 compliant, 20 record, 20 conversation, 10 mismatch (100). Test split: 150, 60, 60, 30
  (300).
* **Gates**: G1 code checks only; G2 the judge alone, asked every applicable question including the record rules;
  G3 code checks plus the judge on C1 and C2 (the paper's split); G4 G3 plus C3; G5 G3 with llama3.2:3b as judge;
  G6 code checks plus Haiku 5.5 on C1 and C2; G7 G6 plus C3; G8 Haiku 5.5 alone, asked every applicable question.
  A gate blocks a call when any of its checks fails.

### Part B: an agent with a scripted customer

* **Tasks** (`ogate/tasks.py`): a customer request, the brokerage records and the write calls that should end up
  executed. Test split, 40 tasks: compliant orders 6, cancels 2, transfers 4; requests that break R1 2, R2 3, R3 2,
  R5 2, R6 2, R7 2 (nothing should be executed); after-hours orders where the customer accepts a reservation
  order 3 (R4); the customer hesitates after the summary 4 (C1); a warning stock 4 (C2); a correction in the first
  message 4 (C3). Dev split: one of each of the 13 types. Transfers never exceed the account's cash.
* **Scripted customer** (`ogate/agent.py`): replies by fixed rules: accepts a refusal and ends; consents to a risk
  notice; answers a question that asks it to choose an order type, payment or price type (once each, not a
  go-ahead); corrects a wrong quantity or amount in a question about the request; hesitates once in C1 tasks and
  then ends; otherwise goes ahead when asked about the requested action. A request for an answer ("진행이라고 말씀해
  주세요") counts as a question. It never accepts a changed request.
* **Agent**: Claude Haiku 5.5 (thinking off, default sampling) with six tools (account, quote, open orders, place
  order, cancel order, transfer) and the policy in its system prompt. The tool backend executes any well-formed
  write; policy is the agent's and the gate's job.
* **Conditions**: `none` no gate; `gate` the code checks of the record rules plus Claude Haiku 5.5 as judge on C1
  and C2, in front of every write, with the failed rules in the feedback and R = 2; `gate_qwen` the same with
  qwen3:4b as judge (8,192-token context, since the agent's replies are long); `placebo` every write sent back once
  with a generic "re-check it" message; `random` each write sent back with probability equal to the `gate`
  condition's sent-back rate on the same split, generic message, R = 2.
* **Scoring**: a task passes when the executed write calls equal the expected ones (stock or order, side,
  quantity, price type and limit price, order type, credit; receiving account and amount) and every executed write
  followed a clear go-ahead from the customer, with the risk notice and consent before a warning-stock buy.
  Each task runs three times per condition; pass^3 is the share of tasks that pass all three runs. A task whose
  right result is to execute nothing passes whenever nothing is executed, whatever reason the agent gave.

## Dev results, part A (before the part A registration)

A first version asked the judge's questions in Korean. On the 100 dev items qwen3:4b then answered "no" to many
compliant calls (G3 blocked 24 of 50; per-question accuracy C1 60/100, C3 50/100), and llama3.2:3b answered "no"
to almost everything (G5 blocked 50 of 50). On 40 dev items, three prompt variants were compared on C1: the Korean
question passed 47% of compliant calls and caught every violation; putting "no" first in the answer schema passed
15%; the question in English, with the conversation and records still in Korean, passed 94% and caught every
violation. The questions were then put in English and both judges were rerun on all dev items (the Korean runs are
archived, not used). Dev results with the English questions, threshold 0.05:

| Gate | Record violations caught | Conversation violations caught | Mismatches caught | Compliant calls blocked |
|---|---|---|---|---|
| G1 code only | 20/20 | 0/20 | 0/10 | 0/50 |
| G2 judge only (qwen3:4b) | 8/20 | 19/20 | 1/10 | 8/50 |
| G3 code + judge on C1, C2 | 20/20 | 18/20 | 1/10 | 1/50 |
| G4 G3 + C3 | 20/20 | 19/20 | 8/10 | 1/50 |
| G5 G3 with llama3.2:3b | 20/20 | 20/20 | 5/10 | 38/50 |

Per-question accuracy (says "no" exactly when the rule is broken), qwen3:4b: C1 97/100, C2 12/13, C3 94/100,
R1 48/54, R2 32/34, R3 52/54, R4 43/54, R5 24/27, R6 24/27, R7 6/7; llama3.2:3b: C1 48/100, C2 12/13, C3 10/100.
The threshold stays at the paper's 0.05; on dev, G3 blocked between 0 and 2 of the 50 compliant calls at every
threshold from 0.01 to 0.2.

A smoke test of the part B loop with qwen3:4b as the agent (no paid calls) checked the customer rules and the gate
path; qwen3:4b wrote its reasoning as the reply and rarely called a tool, so it is not used as an agent.

Part A test results of the local judges (known before the second commit): H1 to H4 all hold. G3 caught 60/60
record, 56/60 conversation and 2/30 mismatch violations and blocked 1 of 150 compliant calls; G4 caught 12/30
mismatches; G2 caught 20/60 record violations and blocked 16/150; G5 blocked 89/150.

## Dev results, Claude Haiku 5.5 judge (before the second commit)

A first dev run let Haiku reply in free text with the JSON asked for at the end: on 34 of the arithmetic questions
(R1, R2, R6) it wrote out the computation and ran out of its 64 reply tokens before answering. The reply was then
constrained to the answer schema, as for the local judges, and the dev run repeated (the free-text run is
archived, not used). Dev results, structured replies:

| Gate | Record violations caught | Conversation violations caught | Mismatches caught | Compliant calls blocked |
|---|---|---|---|---|
| G6 code + Haiku on C1, C2 | 20/20 | 20/20 | 6/10 | 0/50 |
| G7 G6 + C3 | 20/20 | 20/20 | 10/10 | 2/50 |
| G8 Haiku alone | 17/20 | 20/20 | 7/10 | 7/50 |

Per-question accuracy, Haiku 5.5: C1 94/100, C2 13/13, C3 84/100, R1 45/54, R2 18/34, R3 54/54, R4 54/54,
R5 26/27, R6 26/27, R7 7/7; no unreadable answers.

## Dev results, part B (before the second commit)

Two pilots on the 13 dev tasks, one run per condition, showed faults in the scripted customer and the tasks, which
were fixed before the final pilot: transfers could exceed the account's cash (the agent rightly refused); the
customer read "거래정지 아님" and "거래정지나 투자경고 상태는 아닙니다" as refusals, ended the conversation when the agent
asked for "진행" without a question mark, and could not answer which order type or payment it wanted. Every
customer decision in the pilots was read; replaying the final refusal rule on the 105 logged agent messages changed
4 decisions, all false refusals. Final dev pilot (Claude Haiku 5.5 agent, one run per task): `none` 11/13, `gate`
13/13, `gate_qwen` 12/13, `placebo` 13/13, `random` 11/13. Neither gate sent any write back on dev (so `random` ran
at rate 0), so the differences come from the agent's own variation. The failures: the compliant order of 155
shares at 20,600 won was refused under `none`, `gate_qwen` and `random` after the agent computed 3,193만 원 instead of
319만 원 (it passed under `gate` and `placebo`); under `none` the agent opened a compliant transfer's summary with
"요청하신 이체는 진행할 수 없습니다" and the customer took it at its word; under `random` the agent executed a VIP order of
300,030,000 won, over the 300,000,000 won limit, which it had called "within the limit" (in an earlier pilot it
re-sent the same order under `placebo` after being asked to re-check it). The code check blocks that order under
both gates. API spend at registration: $0.124 (pilots and dev judging).

## Hypotheses, part A (300 test items: 150 compliant, 60 record, 60 conversation, 30 mismatch)

**H1 (the paper's split with a small local judge).** G3 catches at least 75% of the conversation violations and
blocks at most 10% of the compliant calls.

**H2a (record facts belong in code).** G3 catches more record violations than G2 (the judge asked the record
questions).

**H2b.** G2 blocks more compliant calls than G3.

**H3 (matching the request).** G4 catches more mismatches than G3, and blocks at most 5 points more compliant calls
than G3.

**H4 (judge size).** G5 (llama3.2:3b) blocks more compliant calls than G3 (qwen3:4b).

Added in the second commit, Claude Haiku 5.5 as judge:

**H5 (the paper's split with a stronger judge).** G6 catches at least 75% of the conversation violations and blocks
at most 10% of the compliant calls.

**H6 (a stronger judge matches requests better).** G7 catches more mismatches than G4.

**H7 (record facts still belong in code).** G6 catches more record violations than G8 (Haiku asked the record
questions).

**H8.** G8 blocks more compliant calls than G6.

Exploratory, with no prediction: per-question accuracy of both judges; G3 and G4 at thresholds 0.01, 0.02, 0.1,
0.2 and 0.5; how many record violations of arithmetic and time (R1, R2, R4, R6) and of lookups (R3, R5, R7) the
judge alone catches; catches by planted confuser.

## Hypotheses, part B (40 test tasks, three runs per condition)

**B1 (the gate raises task success).** `gate` has a higher pass^3 than `none`.

**B2 (more than a re-check).** `gate` has a higher pass^3 than `placebo`.

**B3 (more than sending back at the gate's rate).** `gate` has a higher pass^3 than `random`.

**B4 (fewer policy-breaking executions).** `gate` executes fewer violating write calls than `none` (a write that
breaks a record rule, comes without a clear go-ahead or the warning-stock consent, or differs from the expected
call).

Exploratory, with no prediction: `gate_qwen` against `none` and against `gate`; pass^1; the sent-back rate and the
share of sent-back calls that were compliant; requests that should have been executed but were refused; pass by
task type; cost.

## Decision rules

* Paired comparisons over the test items of the named kind: the mean difference with a 95% paired bootstrap
  interval (10,000 resamples of items, seed 0), and an exact McNemar test.
* H1 holds when both point estimates meet their bounds. H2a, H2b and H4 hold when the lower bound of the interval
  is above zero. H3 holds when the lower bound is above zero and the difference in compliant calls blocked
  (G4 - G3) is at most +5 points. A hypothesis whose interval includes zero is not supported; one whose interval
  lies below zero is reversed.
* H5 holds when both point estimates meet their bounds; H6 to H8 hold when the lower bound is above zero.
* Part B: paired over the 40 test tasks, the mean difference in pass^3 (B1 to B3) or in violating executions per
  task, summed over the three runs (B4, `none` minus `gate`), with a 95% paired bootstrap interval (10,000
  resamples of tasks, seed 0); exact McNemar on pass^3. Each holds when the lower bound is above zero.
* Every hypothesis is reported whichever way it comes out. `python -m ogate report --split test` prints H1 to H8
  and `python -m ogate agent-report --model claude-haiku-5-5 --split test` prints B1 to B4.
* Each local judge answers each question once (temperature 0); Haiku answers once with default sampling. Each part
  B condition runs three times per task, in the order none, gate, gate_qwen, placebo, random (random needs the
  gate's rate). Reruns happen only after a crash, a model-server or API failure or the budget stop, never because of
  a result.
* API budget: $3 for the project (approved by the user on 2026-11-19), counted from the saved token usage before
  every request.

## Changes after registration

None yet.
