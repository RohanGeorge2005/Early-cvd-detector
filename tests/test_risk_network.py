from __future__ import annotations

import unittest

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from src.data_processing import FEATURES
from src.risk_network import _fdr_bh, build_risk_network


class RiskNetworkTests(unittest.TestCase):
    def test_benjamini_hochberg_values_are_adjusted_and_monotone_in_rank(self):
        adjusted = _fdr_bh([.01, .04, .03])
        np.testing.assert_allclose(adjusted, [.03, .04, .04])

    def make_correlated_frame(self, rows: int = 500) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        frame = pd.DataFrame({feature: rng.normal(size=rows) for feature in FEATURES})
        frame["gender"] = rng.integers(0, 2, rows)
        frame["currentSmoker"] = rng.integers(0, 2, rows)
        frame["BPMeds"] = rng.integers(0, 2, rows)
        frame["prevalentStroke"] = rng.integers(0, 2, rows)
        frame["prevalentHyp"] = rng.integers(0, 2, rows)
        frame["diabetes"] = rng.integers(0, 2, rows)
        frame["age"] = np.arange(rows, dtype=float)
        frame["sysBP"] = frame["age"] * 1.4 + rng.normal(0, 4, rows)
        frame["cigsPerDay"] = frame["cigsPerDay"].astype(float)
        frame.loc[:24, "cigsPerDay"] = np.nan
        frame["TenYearCHD"] = frame["age"]  # Must never participate in nodes or edges.
        return frame

    def test_predictors_only_and_fdr_significant_edges(self):
        result = build_risk_network(self.make_correlated_frame())
        ids = {node["id"] for node in result["nodes"]}
        self.assertEqual(ids, set(FEATURES))
        self.assertTrue(result["target_excluded"])
        self.assertNotIn("TenYearCHD", ids)
        pair = next(edge for edge in result["edges"] if {edge["source"], edge["target"]} == {"age", "sysBP"})
        self.assertGreater(pair["correlation"], .9)
        self.assertLessEqual(pair["q_value"], .05)
        self.assertEqual(pair["sample_size"], 500)
        self.assertIn("asymptotic", result["p_value_method"])
        self.assertLessEqual(pair["p_value"], pair["q_value"])

    def test_pairwise_missing_data_count_and_binary_summary(self):
        frame = self.make_correlated_frame()
        frame.loc[:49, "gender"] = np.nan
        result = build_risk_network(frame)
        gender = next(node for node in result["nodes"] if node["id"] == "gender")
        self.assertEqual(gender["statistics"]["observations"], 450)
        self.assertEqual(gender["statistics"]["missing"], 50)
        self.assertEqual(gender["statistics"]["value_one_label"], "Male")
        age_gender = [edge for edge in result["edges"] if {edge["source"], edge["target"]} == {"age", "gender"}]
        if age_gender:
            self.assertEqual(age_gender[0]["sample_size"], 450)
            self.assertEqual(age_gender[0]["method"], "Spearman rank correlation")

    def test_constant_values_return_nodes_without_arbitrary_edges(self):
        frame = pd.DataFrame({feature: np.ones(250) for feature in FEATURES})
        result = build_risk_network(frame)
        self.assertEqual(result["feature_count"], len(FEATURES))
        self.assertEqual(result["edge_count"], 0)

    def test_api_returns_actual_dataset_and_excludes_target(self):
        response = TestClient(app).get("/risk-factor-network")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["rows"], 4240)
        self.assertEqual(result["feature_count"], 15)
        self.assertTrue(result["target_excluded"])
        self.assertNotIn("TenYearCHD", {node["id"] for node in result["nodes"]})
        self.assertGreater(result["edge_count"], 0)


if __name__ == "__main__":
    unittest.main()
