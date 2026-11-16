# Tests

One folder per test, each with its own README (what it answers, conditions, method, pass
conditions) and its own results.

| Folder | Test |
| --- | --- |
| [2026-10-config](2026-10-config/README.md) | The configuration round (from 25 Oct 2026): engine, model, quantization, thinking, harness and topology per workload, for a routing table |
| [2026-11-models](2026-11-models/README.md) | The best model for each task: project management, Python, Swift and a website; local and cloud models |

All tests on one page: http://192.168.50.100:18100/tests/ (Sherlock's demo server), with each test's round pages under it (/tests/<test>/round<n>/) and the files to reproduce the current test. `sh publish.sh` on Sherlock updates it, and rebuilds it after the demo server restarts.
