import unittest

from image_metadata_analyzer.utils import aggregate_focal_lengths


class TestAggregation(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(aggregate_focal_lengths([]), [])

    def test_single_value(self):
        self.assertEqual(aggregate_focal_lengths([50.0]), [("50 mm", 1, 50.0)])

    def test_no_aggregation_needed(self):
        # 3 values, default max_buckets=25
        data = [24.0, 35.0, 50.0]
        result = aggregate_focal_lengths(data)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("24 mm", 1, 24.0))

    def test_aggregation_logic(self):
        # Case where aggregation is forced by small bucket limit
        data = [10.0, 11.0, 20.0, 21.0, 30.0, 31.0]
        # Request 3 buckets.
        # Ideally: (10,11), (20,21), (30,31)
        result = aggregate_focal_lengths(data, max_buckets=3)
        self.assertEqual(len(result), 3)
        # Check counts
        self.assertEqual(result[0][1], 2)
        self.assertEqual(result[1][1], 2)
        self.assertEqual(result[2][1], 2)
        # Check labels
        self.assertEqual(result[0][0], "10-11 mm")
        self.assertEqual(result[1][0], "20-21 mm")
        self.assertEqual(result[2][0], "30-31 mm")

    def test_user_example(self):
        # 16mm vs 20mm (25% diff) should stay separate if threshold allows
        # 300mm vs 304mm (1.3% diff) should merge

        # We need to construct a dataset where this logic holds.
        # If we have [16, 20, 300, 304] and ask for 4 buckets, no aggregation.
        # If we ask for 3 buckets, we need to merge something.
        # The algo should find a threshold that merges 300+304 first because the relative diff is smaller.

        data = [16.0, 20.0, 300.0, 304.0]
        result = aggregate_focal_lengths(data, max_buckets=3)

        # Should contain: 16, 20, 300-304
        self.assertEqual(len(result), 3)

        vals = [r[2] for r in result]
        self.assertIn(16.0, vals)
        self.assertIn(20.0, vals)
        self.assertIn(300.0, vals)

        # Verify 300-304 merged
        last = result[-1]
        self.assertEqual(last[1], 2)  # count 2
        self.assertEqual(last[2], 300.0)  # sort key 300
        self.assertEqual(last[0], "300-304 mm")

    def test_formatting(self):
        data = [10.5, 10.5, 11.2]
        # Force aggregation
        result = aggregate_focal_lengths(data, max_buckets=1)
        # Label should handle floats
        self.assertEqual(result[0][0], "10.5-11.2 mm")

    def test_exact_integers(self):
        data = [50.0, 50.0]
        result = aggregate_focal_lengths(data, max_buckets=10)
        self.assertEqual(result[0][0], "50 mm")


if __name__ == "__main__":
    unittest.main()
