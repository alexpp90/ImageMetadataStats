## 2024-05-18 - Replacing `bin(h1 ^ h2).count("1")` with `.bit_count()`
**Learning:** In Python 3.10+, calculating the population count (Hamming distance) using `int.bit_count()` is significantly faster (approx. 4-5x speedup) than the legacy `bin(val).count("1")` method, as `.bit_count()` is implemented in C.
**Action:** When calculating Hamming distance for image hashes, use `(h1 ^ h2).bit_count()` for performance and maintainability.
