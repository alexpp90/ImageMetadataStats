## 2024-08-07 - Optimize Hamming Distance Calculation
**Learning:** In Python 3.10+, calculating the population count (Hamming distance) using `int.bit_count()` is implemented in C and runs significantly faster (approx. 4-5x speedup) compared to the older `bin(val).count('1')` string conversion method.
**Action:** Always prefer `.bit_count()` on integer XOR results for performance-critical path code.
