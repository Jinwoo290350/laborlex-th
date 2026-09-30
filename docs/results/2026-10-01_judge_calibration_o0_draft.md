# Judge calibration — 2026-10-01 02:10

rows: 60 (offset 0, reference draft) · models {'ch': 20, 'cl': 20, 'g': 20} · lawyer PASS 30

| criterion | exact agreement | weighted κ | lawyer=2 | judge=2 |
|---|---|---|---|---|
| A1 | 85% | 0.00 | 51 | 60 |
| A2 | 50% | 0.20 | 42 | 41 |
| B0 | 78% | -0.10 | 51 | 56 |
| B1 | 70% | 0.28 | 40 | 33 |
| B2 | 67% | 0.23 | 44 | 41 |
| B3 | 60% | 0.26 | 43 | 41 |

- **PASS agreement: 58%** · judge PASS when lawyer FAIL (too lenient): 12 · judge FAIL when lawyer PASS (too strict): 13 · both PASS: 17
- acceptance (κ ≥ 0.6 every criterion and PASS agreement ≥ 80%): **NOT MET**
- cost: 60 calls, in 131458 / out 10124 tokens
