"""Tabular analytics: CSV loading, EDA summaries and anomaly detection."""

from __future__ import annotations

import io
import logging
import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

DEFAULT_CONTAMINATION = 0.05
#: The UI slider and the API endpoint both accept this range only.
MIN_CONTAMINATION = 0.01
MAX_CONTAMINATION = 0.20
MAX_PREVIEW_ROWS = 5
MAX_OUTLIER_SAMPLES = 10
#: Columns whose lower-case name contains one of these substrings are labels or
#: identifiers, not features: modelling them leaks the answer into the model.
LEAKY_COLUMN_MARKERS = ("truth", "label", "target", "is_anomaly", "id")
#: Categorical columns with more levels than this are ignored in the breakdown.
MAX_CATEGORY_LEVELS = 50
#: Last-resort encoding so that legacy Excel exports do not hard-fail ingestion.
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


class DatasetError(ValueError):
    """Raised when a CSV cannot be parsed or lacks the data required for analysis."""


# ---------------------------------------------------------------------------
# Feature selection (label-leakage guard)
# ---------------------------------------------------------------------------
def is_leaky_column(name: Any) -> bool:
    """True when a column name marks it as a label, target or identifier."""
    lowered = str(name).strip().lower()
    return any(marker in lowered for marker in LEAKY_COLUMN_MARKERS)


def split_model_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Split columns into modelling features and excluded (leaky) columns.

    Returns ``(feature_columns, excluded_columns)`` where ``feature_columns``
    are the numeric, non-leaky columns suitable for IsolationForest and
    ``excluded_columns`` is every column flagged as a label/target/id.
    """
    leaky = [str(name) for name in df.columns if is_leaky_column(name)]
    leaky_set = set(leaky)
    features = [
        str(name)
        for name in df.select_dtypes(include=[np.number]).columns
        if str(name) not in leaky_set
    ]
    return features, leaky


def numeric_feature_columns(df: pd.DataFrame) -> list[str]:
    """Numeric columns eligible for modelling (leaky columns removed)."""
    features, _ = split_model_columns(df)
    return features


def _resolve_features(
    df: pd.DataFrame, feature_columns: list[str] | None
) -> tuple[list[str], list[str]]:
    """Validate a user-chosen feature list against the dataset.

    Unknown or leaky names are dropped rather than trusted, so a caller can
    never re-introduce a label column by passing it explicitly.
    """
    candidates, excluded = split_model_columns(df)
    if feature_columns is None:
        return candidates, excluded

    chosen: list[str] = []
    for name in feature_columns:
        text = str(name)
        if text in candidates and text not in chosen:
            chosen.append(text)
    if not chosen:
        raise DatasetError(
            "None of the selected columns can be used as features. Pick at least "
            "one numeric column."
        )
    return chosen, excluded


# ---------------------------------------------------------------------------
# JSON sanitisation
# ---------------------------------------------------------------------------
def sanitize(value: Any) -> Any:
    """Convert numpy / pandas / NaN values into JSON-safe primitives."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        timestamp = pd.Timestamp(value)
        return None if pd.isna(timestamp) else timestamp.isoformat()
    if isinstance(value, (list, tuple, set)):
        return [sanitize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def sanitize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitise a list of row dictionaries."""
    return [{str(key): sanitize(value) for key, value in record.items()} for record in records]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_dataframe(csv_bytes: bytes) -> pd.DataFrame:
    """Parse CSV bytes into a DataFrame with helpful, user-facing errors."""
    if not csv_bytes or not csv_bytes.strip():
        raise DatasetError("The uploaded CSV file is empty.")

    last_error: Exception | None = None
    for encoding in CSV_ENCODINGS:
        try:
            frame = pd.read_csv(
                io.BytesIO(csv_bytes),
                encoding=encoding,
                on_bad_lines="warn",
                low_memory=False,
            )
        except pd.errors.EmptyDataError as exc:
            raise DatasetError("The uploaded CSV contains no data.") from exc
        except pd.errors.ParserError as exc:
            last_error = exc
            continue
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception as exc:  # pragma: no cover - unexpected parser failure
            raise DatasetError(f"Could not read the CSV file: {exc}") from exc

        if frame.shape[0] == 0:
            raise DatasetError("The uploaded CSV contains no rows.")
        if frame.shape[1] == 0:
            raise DatasetError("The uploaded CSV contains no columns.")

        frame.columns = [str(column).strip() for column in frame.columns]
        return frame

    raise DatasetError(f"Could not parse the CSV file: {last_error}")


# ---------------------------------------------------------------------------
# EDA
# ---------------------------------------------------------------------------
def summarize_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """Return a JSON-safe EDA summary: shape, per-column quality, stats, preview."""
    if df is None or df.empty:
        raise DatasetError("Cannot summarise an empty dataset.")

    row_count = int(df.shape[0])
    col_count = int(df.shape[1])

    columns: list[dict[str, Any]] = []
    missing_values: dict[str, int] = {}
    for name in df.columns:
        series = df[name]
        missing = int(series.isna().sum())
        missing_values[str(name)] = missing
        columns.append(
            {
                "name": str(name),
                "dtype": str(series.dtype),
                "non_null": int(series.notna().sum()),
                "missing": missing,
                "missing_pct": round(missing / row_count * 100, 2) if row_count else 0.0,
                "unique": int(series.nunique(dropna=True)),
            }
        )

    try:
        # ``orient="dict"`` is the pandas 2.x/3.x compatible spelling of the old
        # ``orient="columns"``, which pandas 3.1 removed.
        described = df.describe(include="all").to_dict(orient="dict")
        summary_stats = {str(key): sanitize(value) for key, value in described.items()}
    except Exception as exc:  # pragma: no cover - exotic dtypes
        logger.warning("describe() failed, continuing without statistics: %s", exc)
        summary_stats = {}

    preview = sanitize_records(df.head(MAX_PREVIEW_ROWS).to_dict(orient="records"))
    # Leaky columns (labels, targets, ids) are never counted as model features.
    numeric_columns, excluded_columns = split_model_columns(df)

    return {
        "row_count": row_count,
        "col_count": col_count,
        "columns": columns,
        "column_names": [str(name) for name in df.columns],
        "missing_values": missing_values,
        "total_missing": int(sum(missing_values.values())),
        "numeric_columns": numeric_columns,
        "excluded_columns": excluded_columns,
        "summary_stats": summary_stats,
        "preview": preview,
    }


def process_dataset(csv_bytes: bytes) -> dict[str, Any]:
    """Load CSV bytes and return the EDA summary (metadata stored in ``datasets``)."""
    return summarize_dataframe(load_dataframe(csv_bytes))


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------
def _round_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 4) if math.isfinite(number) else None


def _group_stats(series: pd.Series) -> dict[str, Any]:
    """min / max / mean / median of one numeric column, computed in pandas."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": int(numeric.size),
        "min": _round_or_none(numeric.min()),
        "max": _round_or_none(numeric.max()),
        "mean": _round_or_none(numeric.mean()),
        "median": _round_or_none(numeric.median()),
    }


def build_anomaly_breakdown(
    df: pd.DataFrame,
    row_mask: np.ndarray,
    feature_columns: list[str],
) -> dict[str, Any]:
    """Tabulate anomalies against the rest of the data, in pandas.

    Returns per-column numeric distributions for anomalous vs normal rows and,
    for each categorical column, the anomaly rate per category alongside the
    overall base rate so a report can state whether a category is
    over-represented. Everything here is computed, never estimated by an LLM.
    """
    total = int(len(df))
    mask = pd.Series(np.asarray(row_mask, dtype=bool), index=df.index)
    anomalies = int(mask.sum())
    base_rate = (anomalies / total) if total else 0.0

    numeric_profile: dict[str, Any] = {}
    for name in feature_columns:
        column = df[name]
        numeric_profile[str(name)] = {
            "anomalous": _group_stats(column[mask]),
            "normal": _group_stats(column[~mask]),
        }

    categorical_breakdown: dict[str, Any] = {}
    for column in df.columns:
        if str(column) in set(feature_columns) or is_leaky_column(column):
            continue
        series = df[column]
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(
            series
        ):
            continue
        levels = series.astype("string").fillna("(missing)")
        if levels.nunique() < 2 or levels.nunique() > MAX_CATEGORY_LEVELS:
            continue

        grouped = pd.DataFrame({"value": levels, "anomaly": mask.to_numpy()}).groupby(
            "value", dropna=False
        )["anomaly"].agg(["size", "sum"])
        rows: list[dict[str, Any]] = []
        for value, counts in grouped.iterrows():
            rows_in_category = int(counts["size"])
            anomalies_in_category = int(counts["sum"])
            rate = anomalies_in_category / rows_in_category if rows_in_category else 0.0
            rows.append(
                {
                    "value": str(value),
                    "rows": rows_in_category,
                    "anomalies": anomalies_in_category,
                    "anomaly_rate": round(rate, 4),
                    "over_representation": (
                        round(rate / base_rate, 3) if base_rate > 0 else None
                    ),
                }
            )
        rows.sort(key=lambda item: item["anomaly_rate"], reverse=True)
        categorical_breakdown[str(column)] = rows

    return {
        "row_count": total,
        "anomaly_count": anomalies,
        "overall_base_rate": round(base_rate, 4),
        "numeric_profile": numeric_profile,
        "categorical_breakdown": categorical_breakdown,
    }


def detect_outliers(
    df: pd.DataFrame,
    contamination: float = DEFAULT_CONTAMINATION,
    feature_columns: list[str] | None = None,
    include_breakdown: bool = False,
    include_row_flags: bool = False,
) -> dict[str, Any]:
    """Run IsolationForest over the selected numeric columns of ``df``.

    Label/target/id columns are always excluded, exact duplicate rows are
    dropped before fitting, and missing values are imputed with each column's
    median. Returned sample records are the original, unmodified values.
    """
    if df is None or df.empty:
        raise DatasetError("Cannot detect anomalies in an empty dataset.")
    contamination = float(contamination)
    if not 0.0 < contamination <= 0.5:
        raise DatasetError("contamination must be greater than 0 and at most 0.5.")

    feature_names, excluded_columns = _resolve_features(df, feature_columns)
    label_by_name = {str(name): name for name in df.columns}
    feature_labels = [label_by_name[name] for name in feature_names]
    all_labels = list(df.columns)

    # -- drop exact duplicate rows, but keep original row positions --------
    work = df.reset_index(drop=True).copy()
    work["__if_row_id__"] = np.arange(len(work))
    reps = work.drop_duplicates(subset=all_labels, keep="first")[
        all_labels + ["__if_row_id__"]
    ].rename(columns={"__if_row_id__": "__if_rep_id__"})
    mapping = work[all_labels + ["__if_row_id__"]].merge(
        reps, on=all_labels, how="left", sort=False
    )

    rep_ids = mapping["__if_rep_id__"].to_numpy(dtype="float64")
    if len(rep_ids) != len(work) or np.isnan(rep_ids).any():
        # Merge could not map every row back; analyse each row independently.
        rep_ids = np.arange(len(work), dtype="float64")
    rep_ids = rep_ids.astype(int)
    unique_ids = np.unique(rep_ids)

    if len(unique_ids) < 3:
        raise DatasetError("Anomaly detection needs at least 3 distinct rows of data.")

    rep_rows = work.iloc[unique_ids][feature_labels]
    matrix = rep_rows.replace([np.inf, -np.inf], np.nan).astype("float64")
    matrix = matrix.dropna(axis=1, how="all")
    if matrix.shape[1] == 0:
        raise DatasetError("All selected numeric columns are empty after cleaning.")

    # Median imputation, computed on the deduplicated rows that are fitted.
    medians = matrix.median(numeric_only=True)
    matrix = matrix.fillna(medians).fillna(0.0)

    values = matrix.to_numpy(dtype=float)
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    try:
        flags = model.fit_predict(values)
        scores = model.decision_function(values)
    except Exception as exc:  # pragma: no cover - sklearn guard
        raise DatasetError(f"Anomaly detection failed: {exc}") from exc

    rep_flags = pd.Series(flags == -1, index=unique_ids)
    rep_scores = pd.Series(scores, index=unique_ids)
    row_mask = rep_flags.reindex(rep_ids).to_numpy(dtype=bool)
    row_scores = rep_scores.reindex(rep_ids).to_numpy(dtype=float)

    anomaly_count = int(row_mask.sum())
    row_count = int(df.shape[0])

    # Lowest decision-function score == most anomalous; surface those first.
    anomaly_positions = np.flatnonzero(row_mask)
    ordered = anomaly_positions[np.argsort(row_scores[anomaly_positions])][:MAX_OUTLIER_SAMPLES]

    sample_outliers: list[dict[str, Any]] = []
    for position in ordered:
        row = df.iloc[int(position)]
        record: dict[str, Any] = {}
        for offset, column in enumerate(df.columns):
            record[str(column)] = sanitize(row.iloc[offset])
        record["row_index"] = int(position)
        record["anomaly_score"] = round(float(row_scores[int(position)]), 4)
        sample_outliers.append(record)

    result: dict[str, Any] = {
        "method": "IsolationForest",
        "contamination": contamination,
        "row_count": row_count,
        "scored_rows": int(len(unique_ids)),
        "deduplicated_rows": int(row_count - len(unique_ids)),
        "numeric_columns": [str(name) for name in matrix.columns],
        "feature_columns": [str(name) for name in matrix.columns],
        "excluded_columns": excluded_columns,
        "anomaly_count": anomaly_count,
        "anomaly_percentage": round(anomaly_count / row_count * 100, 2) if row_count else 0.0,
        "sample_size": len(sample_outliers),
        "sample_outliers": sample_outliers,
    }
    if include_breakdown:
        result["breakdown"] = build_anomaly_breakdown(
            df, row_mask, [str(name) for name in matrix.columns]
        )
    if include_row_flags:
        # Used by the benchmark to score flags against ground truth.
        result["row_is_anomaly"] = [bool(flag) for flag in row_mask]
    return result


__all__ = [
    "DEFAULT_CONTAMINATION",
    "DatasetError",
    "LEAKY_COLUMN_MARKERS",
    "MAX_CONTAMINATION",
    "MIN_CONTAMINATION",
    "build_anomaly_breakdown",
    "detect_outliers",
    "is_leaky_column",
    "load_dataframe",
    "numeric_feature_columns",
    "process_dataset",
    "sanitize",
    "sanitize_records",
    "split_model_columns",
    "summarize_dataframe",
]
