# Load test 2026-10-25 17:39 UTC

Target http://127.0.0.1:8000; 500 candidates, ramp 60 s, steady 240 s, time speed x1.0 (intervals divided by it), 60% desktop, 10% scripted misbehaviour, ~50 KB images, 2 client processes.

Candidates ready: 500 of 500. Elapsed 320 s.

| Target (spec 10) | Result | Verdict |
| --- | --- | --- |
| API p95 < 300 ms | 13289 ms | **miss** |
| Upload success >= 99 % | 100.00% (6063/6063) | pass |
| Capture -> flag on live wall p95 < 15 s | 33.8 s (n=516) | **miss** |

| Call | Count | p50 ms | p95 ms | p99 ms | Errors |
| --- | --- | --- | --- | --- | --- |
| complete | 6069 | 3390 | 14185 | 22512 | 6 |
| consent | 500 | 16 | 2580 | 6279 | 0 |
| events | 8993 | 1814 | 12549 | 19448 | 3 |
| exchange | 500 | 16 | 2150 | 4939 | 0 |
| finish | 500 | 1223 | 6055 | 10920 | 0 |
| heartbeat | 6733 | 2548 | 13021 | 20878 | 2 |
| live_wall | 82 | 1382 | 3747 | 5649 | 1 |
| precheck | 500 | 50 | 2793 | 6896 | 0 |
| presign | 6075 | 3506 | 14712 | 23466 | 6 |
| put | 6069 | 488 | 4728 | 6593 | 0 |

Error statuses: complete 0: 6, events 0: 3, heartbeat 0: 2, live_wall 0: 1, presign 0: 6
