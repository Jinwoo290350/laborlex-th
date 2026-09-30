# DecisionModel bake-off — node ⑤ select_citations (2026-09-30)

Setup: 30 dev100 questions (first 30 with gold), 15 hybrid candidates each (450 pairs, 73 gold).
Question (noul): "บทบัญญัตินี้เป็นกฎหมายที่ต้องใช้วินิจฉัยคำถามนี้โดยตรงหรือไม่", state = question + provision.

| Decider | AUC | ECE | best F1 (P / R) | gold R@5 retrieval order | gold R@5 decider order | cost |
|---|---|---|---|---|---|---|
| OpenThai-SystemOne v0.3 (hosted) | 0.655 | 0.095 | 0.348 (0.225 / 0.767 @ 0.10) | 0.721 | **0.651** | free (1,000/day) |
| Gemini 3.5 Flash | — | — | — | — | — | not run (no credit) |
| Jev 1.13.0 | — | — | — | — | — | no access |

Spot checks (dismissal case, 4 years of service): ม.41 applies → 0.01 ✓ · ม.17 วรรคสอง → 0.47 · ม.118 → 0.16 ✗ ·
"4 years meets the severance tenure threshold" → not_met 0.94 ✗ (0.8B model, no numeric/legal reasoning).

Decision: OpenThai re-ranking hurts gold recall, so DECIDER=gemini (batch per issue) for now.
Re-run with Gemini once credit is available; revisit OpenThai v0.4 / OpenThai 2.0 Legal.
