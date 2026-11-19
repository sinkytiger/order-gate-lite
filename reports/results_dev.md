# Gate results (dev split, 100 items, threshold P(yes) <= 0.05)

| Gate | What | Record violations caught | Conversation violations caught | Mismatches caught | Compliant calls blocked |
|---|---|---|---|---|---|
| G1 | code checks only | 20/20 = 100.0% (83.9–100.0) | 0/20 = 0.0% (0.0–16.1) | 0/10 = 0.0% (0.0–27.8) | 0/50 = 0.0% (0.0–7.1) |
| G2 | judge questions only (qwen3:4b, record facts asked too) | 8/20 = 40.0% (21.9–61.3) | 19/20 = 95.0% (76.4–99.1) | 1/10 = 10.0% (1.8–40.4) | 8/50 = 16.0% (8.3–28.5) |
| G3 | code + judge on C1, C2 (the paper's split) | 20/20 = 100.0% (83.9–100.0) | 18/20 = 90.0% (69.9–97.2) | 1/10 = 10.0% (1.8–40.4) | 1/50 = 2.0% (0.4–10.5) |
| G4 | G3 + the request-matching question C3 | 20/20 = 100.0% (83.9–100.0) | 19/20 = 95.0% (76.4–99.1) | 8/10 = 80.0% (49.0–94.3) | 1/50 = 2.0% (0.4–10.5) |
| G5 | G3 with llama3.2:3b as judge | 20/20 = 100.0% (83.9–100.0) | 20/20 = 100.0% (83.9–100.0) | 5/10 = 50.0% (23.7–76.3) | 38/50 = 76.0% (62.6–85.7) |

Caught by rule (violating items):

| Gate | R1 | R2 | R3 | R4 | R5 | R6 | R7 | C1 | C2 | C3 |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | 2/2 | 2/2 | 5/5 | 2/2 | 5/5 | 3/3 | 1/1 | 0/16 | 0/4 | 0/10 |
| G2 | 0/2 | 2/2 | 4/5 | 0/2 | 2/5 | 0/3 | 0/1 | 15/16 | 4/4 | 1/10 |
| G3 | 2/2 | 2/2 | 5/5 | 2/2 | 5/5 | 3/3 | 1/1 | 15/16 | 3/4 | 1/10 |
| G4 | 2/2 | 2/2 | 5/5 | 2/2 | 5/5 | 3/3 | 1/1 | 16/16 | 3/4 | 8/10 |
| G5 | 2/2 | 2/2 | 5/5 | 2/2 | 5/5 | 3/3 | 1/1 | 16/16 | 4/4 | 5/10 |

Per-question accuracy, qwen3:4b (correct = says 'no' exactly when the rule is broken):

C1 97/100, C2 12/13, C3 94/100, R1 48/54, R2 32/34, R3 52/54, R4 43/54, R5 24/27, R6 24/27, R7 6/7; unreadable answers 0

Per-question accuracy, llama3.2:3b (correct = says 'no' exactly when the rule is broken):

C1 48/100, C2 12/13, C3 10/100; unreadable answers 0

## Pre-registered checks (part A)

- H1: G3 catches 90.0% of conversation violations (needs >= 75%) and blocks 2.0% of compliant calls (needs <= 10%): holds
- H2a: G3 - G2 on record items = +60.0 pp (+40.0 to +80.0), McNemar 12/0, p = 0.000: holds
- H2b: G2 - G3 on ok items = +14.0 pp (+6.0 to +24.0), McNemar 7/0, p = 0.016: holds
- H3: G4 - G3 on mismatch items = +70.0 pp (+40.0 to +100.0), McNemar 7/0, p = 0.016; compliant calls blocked G4 - G3 = +0.0 pp (needs <= +5): holds
- H4: G5 - G3 on ok items = +74.0 pp (+62.0 to +86.0), McNemar 37/0, p = 0.000: holds

Exploratory: G3 at other thresholds (the registered threshold is 0.05):

| Threshold | Conversation violations caught | Mismatches caught by G4 | Compliant blocked by G3 | Compliant blocked by G4 |
|---|---|---|---|---|
| 0.01 | 15/20 | 3/10 | 0/50 | 0/50 |
| 0.02 | 16/20 | 5/10 | 0/50 | 0/50 |
| 0.05 | 18/20 | 8/10 | 1/50 | 1/50 |
| 0.1 | 18/20 | 9/10 | 1/50 | 2/50 |
| 0.2 | 18/20 | 10/10 | 2/50 | 3/50 |
| 0.5 | 19/20 | 10/10 | 26/50 | 29/50 |

Exploratory: the judge alone (G2) catches 2/9 record violations of arithmetic and time (R1, R2, R4, R6).

Exploratory: the judge alone (G2) catches 6/11 record violations of lookups (R3, R5, R7).