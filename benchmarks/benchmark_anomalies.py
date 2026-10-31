"""Benchmark IsolationForest precision / recall / F1 on synthetic metrics data.

Usage (from the ``insightforge`` directory):

    python benchmarks/benchmark_anomalies.py

The dataset (``complex_metrics_test.csv``) is synthetic: 601 rows of service
metrics with 27 deliberately injected multi-dimensional outliers and an
``is_anomaly`` ground-truth column. That column is excluded from modelling by
``backend.analytics`` (name contains "is_anomaly"), so it is only used here to
score the predictions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import analytics  # noqa: E402

CSV_PATH = Path(__file__).with_name("complex_metrics_test.csv")
CONTAMINATIONS = (0.02, 0.05, 0.10)
TRUTH_NAMES = ("is_anomaly", "anomaly", "label", "target", "truth")


def find_truth_column(frame) -> str:
    for name in frame.columns:
        if str(name).strip().lower() in TRUTH_NAMES:
            return str(name)
    raise SystemExit(f"No ground-truth column found; expected one of {TRUTH_NAMES}.")


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    frame = analytics.load_dataframe(CSV_PATH.read_bytes())
    truth_column = find_truth_column(frame)
    truth = frame[truth_column].fillna(0).astype(int).to_numpy(dtype=bool) == 1

    print(
        f"Dataset: {CSV_PATH.name} | rows={len(frame)} | "
        f"true anomalies={int(truth.sum())} ({truth.mean() * 100:.2f}%)"
    )
    print(f"Ground truth column (never used as a feature): {truth_column}")
    print()
    print("| Contamination | Flagged | TP | FP | FN | Precision | Recall | F1 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")

    for contamination in CONTAMINATIONS:
        result = analytics.detect_outliers(
            frame, contamination=contamination, include_row_flags=True
        )
        flags = np.asarray(result["row_is_anomaly"], dtype=bool)
        tp = int(np.count_nonzero(flags & truth))
        fp = int(np.count_nonzero(flags & ~truth))
        fn = int(np.count_nonzero(~flags & truth))
        precision = ratio(tp, tp + fp)
        recall = ratio(tp, tp + fn)
        f1 = ratio(2 * precision * recall, precision + recall)
        print(
            f"| {contamination:.2f} | {int(flags.sum())} | {tp} | {fp} | {fn} | "
            f"{precision:.3f} | {recall:.3f} | {f1:.3f} |"
        )


if __name__ == "__main__":
    main()
