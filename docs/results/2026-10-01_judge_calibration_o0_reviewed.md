# Judge calibration — 2026-10-01 02:07

rows: 60 (offset 0) · models {'ch': 20, 'cl': 20, 'g': 20} · lawyer PASS 30

| criterion | exact agreement | weighted κ | lawyer=2 | judge=2 |
|---|---|---|---|---|
| A1 | 85% | 0.00 | 51 | 60 |
| A2 | 55% | 0.06 | 42 | 38 |
| B0 | 73% | -0.15 | 51 | 53 |
| B1 | 53% | 0.11 | 40 | 26 |
| B2 | 63% | 0.13 | 44 | 38 |
| B3 | 60% | 0.07 | 43 | 37 |

- **PASS agreement: 58%** · judge PASS when lawyer FAIL (too lenient): 9 · judge FAIL when lawyer PASS (too strict): 16 · both PASS: 14
- acceptance (κ ≥ 0.6 every criterion and PASS agreement ≥ 80%): **NOT MET**
- cost: 60 calls, in 127760 / out 10315 tokens
