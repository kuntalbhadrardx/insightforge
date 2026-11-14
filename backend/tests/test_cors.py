"""The deployed frontend lives on generated Vercel preview URLs; nothing else
may be allowed to call the API with credentials."""

from __future__ import annotations

import json
import re

import pandas as pd
import pytest

from backend import agent, analytics, main

ORIGIN = re.compile(main.ALLOWED_ORIGIN_REGEX)


@pytest.mark.parametrize(
    "origin",
    [
        "https://insightforge.vercel.app",
        "https://insightforge-preview.vercel.app",
        "https://insightforge-git-main-kuntal.vercel.app",
        "https://insightforge-pr-42.vercel.app"
    ]
)
def test_generated_project_origins_are_allowed(origin):
    assert ORIGIN.match(origin)


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example.com",
        "https://insightforge.vercel.app.evil.com",
        "https://insightforge-.vercel.app",
        "http://insightforge-preview.vercel.app",
        "https://notinsightforge-preview.vercel.app",
        "https://insightforge-preview.vercel.app/"
    ]
)
def test_other_origins_are_blocked(origin):
    assert not ORIGIN.match(origin)


def outlier_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "value": [10.0, 10.1, 9.8, 10.2, 9.9, 10.0, 10.3, 9.7, 10.1, 80.0],
            "temperature": [20, 21, 19, 20, 22, 21, 20, 19, 21, 21],
            "patient_id": [f"P{index}" for index in range(10)],
            "note": ["routine"] * 9 + ["SSN-999-99-9999"]
        }
    )


def test_anomaly_breakdown_never_tabulates_single_occurrence_values():
    result = analytics.detect_outliers(
        outlier_frame(), contamination=0.2, include_breakdown=True
    )

    # The breakdown is an aggregate report. A value seen once is a cell copied
    # out of the file, so its column is dropped rather than tabulated.
    breakdown = json.dumps(result["breakdown"], default=str)
    assert "SSN-999-99-9999" not in breakdown
    assert "P4" not in breakdown
    assert result["anomaly_count"] >= 1
    assert result["row_count"] == 10

    # Row-level detail exists, but only in the dedicated list the dashboard
    # table renders -- never inside the statistics.
    assert result["sample_size"] == len(result["sample_outliers"])
    assert all("row_index" in row for row in result["sample_outliers"])


def test_agent_detect_anomalies_tool_is_aggregate_only():
    session = agent._ToolSession(
        user_id="user-1", dataset_df=outlier_frame(), document_id=None
    )

    payload = session.detect_anomalies({"contamination": 0.2})

    assert set(payload) == {
        "method",
        "contamination",
        "row_count",
        "scored_rows",
        "deduplicated_rows",
        "imputation",
        "feature_columns",
        "excluded_columns",
        "anomaly_count",
        "anomaly_percentage",
        "breakdown"
    }
    assert "SSN-999-99-9999" not in json.dumps(payload, default=str)
    assert "patient_id" in payload["excluded_columns"]
