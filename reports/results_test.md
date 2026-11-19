# Gate results (test split, 300 items, threshold P(yes) <= 0.05)

| Gate | What | Record violations caught | Conversation violations caught | Mismatches caught | Compliant calls blocked |
|---|---|---|---|---|---|
| G1 | code checks only | 60/60 = 100.0% (94.0–100.0) | 0/60 = 0.0% (0.0–6.0) | 0/30 = 0.0% (0.0–11.4) | 0/150 = 0.0% (0.0–2.5) |
| G2 | judge questions only (qwen3:4b, record facts asked too) | 20/60 = 33.3% (22.7–45.9) | 57/60 = 95.0% (86.3–98.3) | 4/30 = 13.3% (5.3–29.7) | 16/150 = 10.7% (6.7–16.6) |
| G3 | code + judge on C1, C2 (the paper's split) | 60/60 = 100.0% (94.0–100.0) | 56/60 = 93.3% (84.1–97.4) | 2/30 = 6.7% (1.8–21.3) | 1/150 = 0.7% (0.1–3.7) |
| G4 | G3 + the request-matching question C3 | 60/60 = 100.0% (94.0–100.0) | 58/60 = 96.7% (88.6–99.1) | 12/30 = 40.0% (24.6–57.7) | 1/150 = 0.7% (0.1–3.7) |
| G5 | G3 with llama3.2:3b as judge | 60/60 = 100.0% (94.0–100.0) | 57/60 = 95.0% (86.3–98.3) | 19/30 = 63.3% (45.5–78.1) | 89/150 = 59.3% (51.3–66.9) |
| G6 | code + judge on C1, C2 (Claude Haiku 5.5) | 60/60 = 100.0% (94.0–100.0) | 60/60 = 100.0% (94.0–100.0) | 20/30 = 66.7% (48.8–80.8) | 1/150 = 0.7% (0.1–3.7) |
| G7 | G6 + C3 (Claude Haiku 5.5) | 60/60 = 100.0% (94.0–100.0) | 60/60 = 100.0% (94.0–100.0) | 30/30 = 100.0% (88.6–100.0) | 9/150 = 6.0% (3.2–11.0) |
| G8 | judge questions only (Claude Haiku 5.5, record facts asked too) | 55/60 = 91.7% (81.9–96.4) | 60/60 = 100.0% (94.0–100.0) | 22/30 = 73.3% (55.6–85.8) | 40/150 = 26.7% (20.2–34.3) |

Caught by rule (violating items):

| Gate | R1 | R2 | R3 | R4 | R5 | R6 | R7 | C1 | C2 | C3 |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | 6/6 | 12/12 | 9/9 | 12/12 | 8/8 | 7/7 | 6/6 | 0/47 | 0/13 | 0/30 |
| G2 | 0/6 | 2/12 | 6/9 | 4/12 | 4/8 | 0/7 | 4/6 | 45/47 | 12/13 | 4/30 |
| G3 | 6/6 | 12/12 | 9/9 | 12/12 | 8/8 | 7/7 | 6/6 | 44/47 | 12/13 | 2/30 |
| G4 | 6/6 | 12/12 | 9/9 | 12/12 | 8/8 | 7/7 | 6/6 | 46/47 | 12/13 | 12/30 |
| G5 | 6/6 | 12/12 | 9/9 | 12/12 | 8/8 | 7/7 | 6/6 | 47/47 | 10/13 | 19/30 |
| G6 | 6/6 | 12/12 | 9/9 | 12/12 | 8/8 | 7/7 | 6/6 | 47/47 | 13/13 | 20/30 |
| G7 | 6/6 | 12/12 | 9/9 | 12/12 | 8/8 | 7/7 | 6/6 | 47/47 | 13/13 | 30/30 |
| G8 | 4/6 | 12/12 | 9/9 | 11/12 | 8/8 | 5/7 | 6/6 | 47/47 | 13/13 | 22/30 |

Per-question accuracy, qwen3:4b (correct = says 'no' exactly when the rule is broken):

C1 294/300, C2 38/39, C3 270/300, R1 185/197, R2 91/106, R3 191/197, R4 162/197, R5 67/71, R6 64/71, R7 28/30; unreadable answers 0

Per-question accuracy, llama3.2:3b (correct = says 'no' exactly when the rule is broken):

C1 154/300, C2 32/39, C3 30/300; unreadable answers 0

Per-question accuracy, claude-haiku-5-5 (correct = says 'no' exactly when the rule is broken):

C1 279/300, C2 38/39, C3 243/300, R1 182/197, R2 56/106, R3 197/197, R4 196/197, R5 66/71, R6 68/71, R7 30/30; unreadable answers 0

## Pre-registered checks (part A)

- H1: G3 catches 93.3% of conversation violations (needs >= 75%) and blocks 0.7% of compliant calls (needs <= 10%): holds
- H2a: G3 - G2 on record items = +66.7 pp (+55.0 to +78.3), McNemar 40/0, p = 0.000: holds
- H2b: G2 - G3 on ok items = +10.0 pp (+5.3 to +14.7), McNemar 15/0, p = 0.000: holds
- H3: G4 - G3 on mismatch items = +33.3 pp (+16.7 to +50.0), McNemar 10/0, p = 0.002; compliant calls blocked G4 - G3 = +0.0 pp (needs <= +5): holds
- H4: G5 - G3 on ok items = +58.7 pp (+50.7 to +66.7), McNemar 88/0, p = 0.000: holds
- H5: G6 catches 100.0% of conversation violations (needs >= 75%) and blocks 0.7% of compliant calls (needs <= 10%): holds
- H6: G7 - G4 on mismatch items = +60.0 pp (+43.3 to +76.7), McNemar 18/0, p = 0.000: holds
- H7: G6 - G8 on record items = +8.3 pp (+1.7 to +16.7), McNemar 5/0, p = 0.062: holds
- H8: G8 - G6 on ok items = +26.0 pp (+19.3 to +33.3), McNemar 39/0, p = 0.000: holds

Exploratory: G3 at other thresholds (the registered threshold is 0.05):

| Threshold | Conversation violations caught | Mismatches caught by G4 | Compliant blocked by G3 | Compliant blocked by G4 |
|---|---|---|---|---|
| 0.01 | 46/60 | 3/30 | 0/150 | 0/150 |
| 0.02 | 50/60 | 9/30 | 0/150 | 0/150 |
| 0.05 | 56/60 | 12/30 | 1/150 | 1/150 |
| 0.1 | 57/60 | 14/30 | 5/150 | 6/150 |
| 0.2 | 57/60 | 17/30 | 8/150 | 13/150 |
| 0.5 | 57/60 | 29/30 | 82/150 | 85/150 |

Exploratory: the judge alone (G2) catches 6/37 record violations of arithmetic and time (R1, R2, R4, R6).

Exploratory: the judge alone (G2) catches 14/23 record violations of lookups (R3, R5, R7).