## 2024-05-18 - Fast Hamming Distance Calculation in Python
**Learning:** In Python 3.10+, calculating the Hamming distance between two integers using `(h1 ^ h2).bit_count()` is significantly faster (~4-5x) than the traditional approach of converting the XOR result to a binary string and counting '1's (`bin(h1 ^ h2).count("1")`) because `bit_count` is implemented in C and avoids expensive string allocation.
**Action:** Always prefer `int.bit_count()` for population counts in Python 3.10+ environments when performance matters, such as in image hashing comparison loops.
