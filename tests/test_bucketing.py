import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.detectors import DetectorRunner, _get_bucket_start


class BucketingTests(unittest.TestCase):
    def test_week_bucket_start_is_datetime(self) -> None:
        sample_dt = datetime(2025, 1, 15, 13, 45, 0)  # Wednesday
        bucket_start = _get_bucket_start(sample_dt, "week")
        self.assertIsInstance(bucket_start, datetime)
        self.assertEqual(bucket_start, datetime(2025, 1, 13, 0, 0, 0))

    def test_run_all_by_bucket_week(self) -> None:
        trades = [
            {
                "proxy_wallet": "0xabc",
                "trade_uid": "t1",
                "ts": datetime(2025, 1, 15, 13, 45, 0),
                "token_id": "token1",
                "condition_id": "cond1",
                "outcome_index": 0,
                "side": "BUY",
                "size": 10.0,
                "price": 0.5,
            }
        ]
        runner = DetectorRunner()
        results = runner.run_all_by_bucket(
            trades=trades,
            proxy_wallet="0xabc",
            bucket_type="week",
            market_tokens_map={},
        )
        self.assertTrue(results)
        for result in results:
            self.assertIsInstance(result.bucket_start, datetime)


if __name__ == "__main__":
    unittest.main()
