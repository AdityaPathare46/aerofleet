# Flight review speed on real PX4 logs

Measured 19 November 2026 on arm64 Darwin 27.0.0, Python 3.10.19. 30 real public PX4 logs from the study's downloaded folders, spread over the size range; 10 could not be read and were skipped. Times cover reading the log, vibration, the evidence timeline and the public comparison (not the database write). Script: `tools/benchmark_review.py`.

| | Value |
|---|---|
| Log sizes | 0.9 to 92.8 MB (median 8.0 MB) |
| Flight lengths | 0.2 to 28.3 min |
| Time per review | median 0.23 s, slowest 2.44 s |
| Largest log | 92.8 MB in 2.44 s |
| Throughput | 35.5 MB/s |
