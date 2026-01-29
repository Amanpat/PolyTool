import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.token_resolution import resolve_token_id


class TokenResolutionTests(unittest.TestCase):
    def test_alias_mapping_resolves_to_canonical(self):
        resolved = resolve_token_id(
            token_id="alias123",
            condition_id="0xabc",
            outcome="Yes",
            direct_token_ids=set(),
            alias_map={"alias123": "clob999"},
            markets_map={},
        )
        self.assertEqual(resolved, "clob999")

    def test_condition_outcome_fallback_resolves(self):
        resolved = resolve_token_id(
            token_id="unknown",
            condition_id="0xABC",
            outcome="No",
            direct_token_ids=set(),
            alias_map={},
            markets_map={
                "0xabc": {
                    "outcomes": ["Yes", "No"],
                    "clob_token_ids": ["clob_yes", "clob_no"],
                }
            },
        )
        self.assertEqual(resolved, "clob_no")


if __name__ == "__main__":
    unittest.main()
