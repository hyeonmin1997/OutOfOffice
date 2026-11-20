# DATA CARD · Team OutOfOffice · test set v1

| Field | Value |
|---|---|
| **purpose** | Proposal §2 threat model: a C0 attacker who can write the body of one mail M reads during onboarding. Goals: forbidden access grant, send outside the allowed recipient, overwrite the saved task (role/target), read another user's mail. |
| **world** | Synthetic. SQLite seed in `data/seed/` (users M, A, B; mails `mail1`, `attack1`, `private_b`; one event). English, plus a Korean out-of-distribution split. One mail per task run. |
| **attacks** | 40 English (dev 20 / test 20) + 4 Korean (ood). Grid: 4 goals × 5 placements × 2 wordings, 1 case per cell per wording. Seeds: hand-written templates (`eval/build_cases.py`); none taken from a benchmark yet. |
| **benign** | 40 English twins (dev 20 / test 20) + 4 Korean twins. Each twin is its attack with only the malicious request replaced by a harmless sentence on the same topic, so false positives are measured on the same surface. No separate "ordinary" benign set yet. |
| **generator** | Templates drafted with Claude Opus 5.5 (Anthropic) on 2026-11-20 and expanded deterministically by `eval/build_cases.py` (no sampling, no temperature). Different model family from the system under test. |
| **system under test** | `qwen2.5:3b` via local Ollama, digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`, Q4_K_M, temperature 0. |
| **judge** | Code check on the final SQLite state (`evaluate.py` oracle), written separately from the server policy. No LLM judge. |
| **agreement** | Not done yet. Planned: two team members label a random sample of cases (is the attack a forbidden request? is the twin harmless?) and report agreement. |
| **baseline** | Defense OFF attack success: dev 25% (5/20 effective attacks), test 10% (2/20). See Results. |
| **split** | dev 40 / test 40 / ood 8. Split by wording: wording 0 → dev, wording 1 → test, so no mail text appears in two splits. Test frozen on 2026-11-20 (commit that adds this card; `cases_sha256` is recorded in every results file). Tune only on dev. |
| **known gaps** | See below. |

## Coverage grid (attacks per split)

| Goal \ Placement | appended | checklist | forwarded | fake_system | footer |
|---|---|---|---|---|---|
| grant | 1 | 1 | 1 | 1 | 1 |
| exfil | 1 | 1 | 1 | 1 | 1 |
| task_overwrite | 1 | 1 | 1 | 1 | 1 |
| read | 1 | 1 | 1 | 1 | 1 |

Out of scope, with reasons:
- **Attachments, calendar invites, shared documents:** the system reads only mail bodies.
- **Attacks spread across several mails:** one mail per task run.
- **Burning the budget:** bounded by call limits (6 per run, 30 per session); measured with the cost cap in Lab 5.
- **Encoded / obfuscated instructions, attacks written outside the team:** listed as outside the test set in the proposal (§5). Coverage there is unknown.
- **Harmful content to an allowed recipient** (e.g. a phishing link in A's welcome mail): not a forbidden action under the current policy; a known residual risk, not measured by this set.

## Results

`qwen2.5:3b` (digest `357c53fb…`), temperature 0, 1 run per case. Defense OFF = tool-format check only; Defense ON = task scope/ACL + exact approval, with a simulated operator who approves every pending request. Oracle v2 (code, final DB state).

| Split · file | Setting | Benign task success | Attack success (ASR) | Unsafe requests | Guard false positives | Approval prompts / benign task |
|---|---|---|---|---|---|---|
| dev · `api_dev_20261120-231923.json` | OFF | 80% (16/20) | 25% (5/20) | 25% (5/20) | — | 0 |
| | ON | 80% (16/20) | **0% (0/20)** | 25% (5/20) | 0 | 1.7 |
| **test** · `api_test_20261121-033450.json` | OFF | 70% (14/20) | 10% (2/20) | 10% (2/20) | — | 0 |
| | ON | 70% (14/20) | **0% (0/20)** | 10% (2/20) | 0 | 1.5 |

- Effective attacks (succeed with Defense OFF): dev 5/20, test 2/20. Defense ON stopped all of them (dev 0/5, test 0/2). The other attacks failed even undefended and are listed as dead in each results file.
- By goal, undefended: exfil succeeded on dev (4/5) but not on test (0/5); task_overwrite 1/5 dev, 2/5 test; grant and read 0/5 on both — the 3B model never attempted them, so these rows do not test the defence.
- Benign forbidden writes: 0 in all runs. Benign task success did not drop with the defence on (dev 80/80, test 70/70) and misses the proposal's 90% target.
- Dev history: `api_dev_20261120-222546.json` is the run before the dev-only prompt fix (the model asked M for the email subject/body); the fix raised Defense OFF benign success 75% → 80%. The test split was run once, after the fix.
- All three files were re-judged with oracle v2 (`evaluate.py --rescore`): v1 counted malformed tool calls as forbidden requests. ASR and task success are unchanged; the v1 summary is kept as `summary_original`.

## Known gaps

- One template author (an LLM, one prompt session) and one team; wording variety is limited (2 wordings per goal). Count strategies, not rows.
- Only 5 placements and one mail per run; a realistic inbox would bury the injection among many mails.
- Small dev/test sets (20 attacks each): one case changes a rate by 5 points.
- Results depend on one 3B model; attacks that fail against it may succeed against stronger models and the reverse. Only 2 test attacks are effective, so the defended ASR of 0/2 is a weak estimate; repeated runs (`--repeats`, temperature > 0) and attacks that the model actually attempts (grant, read) are needed.
- Exfil worked on dev wording but not on test wording: the effect depends on phrasing, which a 2-wording grid samples poorly.
- A fixed set measures the attacks we thought of; adaptive attackers (Weeks 14–15) are the test it cannot replace.
