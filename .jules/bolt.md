## 2024-08-12 - [Python 3.10+ Fast Hamming Distance]
**Learning:** In Python 3.10+, `int.bit_count()` is significantly faster (approx. 4-5x speedup) than `bin(val).count('1')` for calculating population count (Hamming distance) because it is implemented in C.
**Action:** Replace `bin(h1 ^ h2).count("1")` with `(h1 ^ h2).bit_count()` in `core/utils.py` to speed up dHash similarity checks.
