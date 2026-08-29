## 2024-05-19 - Optimize Hamming distance
**Learning:** Python 3.10+ int.bit_count() is significantly faster than bin().count("1") for population count.
**Action:** Use int.bit_count() instead of bin().count("1") for Hamming distance calculations.
