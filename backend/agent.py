"""Groq tool-calling agent that plans research and data-analysis tasks.

The agent exposes three Python tools to ``llama-3.1-8b-instant``:

* ``search_papers``    -- pgvector similarity search over the user's paper chunks
* ``describe_data``    -- column/types/null inspection of the active dataset
* ``detect_anomalies`` -- IsolationForest run over the active dataset

``run_agent_workflow`` drives a bounded multi-turn loop, executes the tools the
model asks for, feeds the results back, then asks for a final Markdown report.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable

from groq import Groq

from . import analytics, db, pdf_rag

logger = logging.getLogger(__name__)

#: Groq retired llama-3.1-8b-instant; gpt-oss-20b is the closest replacement in
#: the same speed class and supports function calling.
MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
MAX_ITERATIONS = 4
MAX_AGENT_TOKENS = 1024
MAX_FINAL_TOKENS = 1500
#: Excerpts are truncated so a handful of matches cannot blow the context window.
MAX_EXCERPT_CHARS = 1200
MAX_TOOL_RESULT_CHARS = 6000
MAX_COLUMNS_IN_TOOL_OUTPUT = 60


def _env_float(name: str, default: float) -> float:
    """Read a float setting, tolerating an unset or blank value."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


TOOL_MATCH_THRESHOLD = _env_float("MATCH_THRESHOLD", 0.05)
#: Excerpts below this similarity are not evidence and must never be cited.
MIN_RELEVANT_SIMILARITY = 0.30

SYSTEM_PROMPT = """You are InsightForge, a meticulous AI research and data-analysis agent.

You have tools available. Use them whenever the answer depends on the user's \
documents or dataset -- never invent paper contents, statistics, or anomalies.
Call a tool only when it is useful, then synthesise a clear answer.

GROUNDING RULES (non-negotiable):
- Only state facts present in tool output. If search_papers returns nothing relevant, say the paper is unrelated to the dataset and make NO connection between them.
- Never cite the paper without a retrieved page number.
- Never claim a pattern holds for 'all' rows unless the computed stats prove it.
- Quote dataset numbers exactly as returned; never do arithmetic, estimate, extrapolate or invent a statistic yourself.
- Never state that a category is over-represented unless its over_representation value in the tool output shows it.
- If a tool returns an error or no data, say so instead of filling the gap.
- Never speculate about data preparation (imputation, deduplication, excluded columns). Only describe preprocessing that a tool reports in its own output.

Final answers must be GitHub-flavoured Markdown with this structure:
## Summary
Two or three sentences answering the goal directly.
## Key findings
Bullet points, each grounded in the tool output.
## Evidence
Cite paper excerpts as `[page N]`; cite dataset numbers as reported by the tools.
## Limitations
State what the available data could not answer.

Be concise and factual. Do not mention internal tool names or JSON payloads."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_papers",
            "description": (
                "Semantic search over the user's uploaded PDF papers. Returns the most "
                "relevant text excerpts with page numbers and similarity scores. If no "
                "excerpt reaches the relevance cut-off it returns status "
                "'no_relevant_passages' with an empty result list - that means the paper "
                "does not cover the query, so do not cite it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A focused natural-language search query.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "How many excerpts to return (1-10). Defaults to 5.",
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_data",
            "description": (
                "Inspect the active CSV dataset: shape, column names and dtypes, null "
                "counts and pandas-computed per-column statistics. Use before "
                "describing or analysing data."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_anomalies",
            "description": (
                "Run IsolationForest anomaly detection on the numeric columns of the "
                "active dataset. Returns computed statistics only: anomaly counts, "
                "anomaly rate per category with the overall base rate, and min/max/mean/"
                "median for anomalous vs normal rows. No raw rows are returned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contamination": {
                        "type": "number",
                        "description": (
                            "Expected share of outliers in the data, from 0.01 to 0.20. "
                            "Defaults to 0.05."
                        ),
                        "minimum": 0.01,
                        "maximum": 0.20,
                    }
                },
                "required": [],
            },
        },
    },
]


class AgentError(RuntimeError):
    """Raised when the agent cannot run (misconfiguration or upstream failure)."""


_client: Groq | None = None


def get_groq_client() -> Groq:
    """Return a cached Groq client, creating it on first use."""
    global _client
    if _client is None:
        api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if not api_key:
            raise AgentError("GROQ_API_KEY is not configured.")
        _client = Groq(api_key=api_key)
    return _client


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def _json_safe(payload: Any) -> Any:
    """Make tool output safe for the Groq request body and the agent_runs column."""
    try:
        encoded = json.dumps(payload, default=analytics.sanitize, allow_nan=False)
    except (TypeError, ValueError):
        encoded = json.dumps(analytics.sanitize(payload), default=str, allow_nan=False)
    return json.loads(encoded)


def _parse_arguments(raw_arguments: str | None) -> tuple[dict[str, Any], str | None]:
    if not raw_arguments:
        return {}, None
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        return {}, f"Arguments were not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return {}, "Arguments must be a JSON object."
    return parsed, None


def _compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Trim an EDA summary to computed metadata and statistics.

    Raw preview rows are deliberately omitted: the report must quote numbers
    that pandas computed, never eyeball individual records.
    """
    columns = summary.get("columns", [])[:MAX_COLUMNS_IN_TOOL_OUTPUT]
    numeric_columns = summary.get("numeric_columns", [])[:MAX_COLUMNS_IN_TOOL_OUTPUT]
    raw_stats = summary.get("summary_stats") or {}

    numeric_stats: dict[str, Any] = {}
    for name in numeric_columns:
        stats = raw_stats.get(name)
        if isinstance(stats, dict):
            numeric_stats[str(name)] = {
                key: analytics.sanitize(stats[key])
                for key in ("count", "mean", "std", "min", "25%", "50%", "75%", "max")
                if key in stats
            }

    return {
        "row_count": summary.get("row_count"),
        "col_count": summary.get("col_count"),
        "columns": [
            {
                "name": column.get("name"),
                "dtype": column.get("dtype"),
                "missing": column.get("missing"),
                "unique": column.get("unique"),
            }
            for column in columns
            if isinstance(column, dict)
        ],
        "truncated_columns": max(0, len(summary.get("columns", [])) - len(columns)),
        "total_missing": summary.get("total_missing"),
        "numeric_columns": numeric_columns,
        "excluded_columns": summary.get("excluded_columns", []),
        "numeric_stats": numeric_stats,
    }


class _ToolSession:
    """Holds the per-request context the tools read from."""

    def __init__(
        self,
        *,
        user_id: str,
        dataset_df: Any | None,
        document_id: str | None,
    ) -> None:
        self.user_id = user_id
        self.dataset_df = dataset_df
        self.document_id = document_id
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "search_papers": self.search_papers,
            "describe_data": self.describe_data,
            "detect_anomalies": self.detect_anomalies,
        }

    # -- tools -------------------------------------------------------------
    def search_papers(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("'query' must be a non-empty string.")

        try:
            top_k = int(arguments.get("top_k", 5))
        except (TypeError, ValueError):
            top_k = 5
        top_k = max(1, min(10, top_k))

        embedding = pdf_rag.embed_query(query)
        matches = db.search_paper_chunks(
            user_id=self.user_id,
            query_embedding=embedding,
            match_threshold=TOOL_MATCH_THRESHOLD,
            match_count=top_k,
            document_id=self.document_id,
        )

        best_similarity = max((float(m["similarity"]) for m in matches), default=0.0)
        # Below the relevance cut-off the chunks are noise, not evidence. Say so
        # rather than handing the model text it may force into a narrative.
        if not matches or best_similarity < MIN_RELEVANT_SIMILARITY:
            return {
                "query": query,
                "count": 0,
                "status": "no_relevant_passages",
                "best_similarity": round(best_similarity, 4),
                "results": [],
                "message": (
                    "No relevant passages found. The paper does not appear to cover "
                    "this query, so it must not be cited or connected to the dataset."
                ),
            }

        relevant = [m for m in matches if float(m["similarity"]) >= MIN_RELEVANT_SIMILARITY]
        results = [
            {
                "document_id": match["document_id"],
                "page_number": match["page_number"],
                "similarity": round(match["similarity"], 4),
                "excerpt": _truncate(match["content"], MAX_EXCERPT_CHARS),
            }
            for match in relevant
        ]
        return {"query": query, "count": len(results), "results": results}

    def describe_data(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.dataset_df is None:
            return {
                "error": "No dataset is attached to this run. Ask the user to upload a CSV first."
            }
        summary = analytics.summarize_dataframe(self.dataset_df)
        return _compact_summary(summary)

    def detect_anomalies(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.dataset_df is None:
            return {
                "error": "No dataset is attached to this run. Ask the user to upload a CSV first."
            }
        raw = arguments.get("contamination", analytics.DEFAULT_CONTAMINATION)
        try:
            contamination = float(raw)
        except (TypeError, ValueError):
            contamination = analytics.DEFAULT_CONTAMINATION
        contamination = min(
            max(contamination, analytics.MIN_CONTAMINATION), analytics.MAX_CONTAMINATION
        )

        result = analytics.detect_outliers(
            self.dataset_df, contamination=contamination, include_breakdown=True
        )
        # Hand the model computed statistics only -- never raw sample rows.
        return {
            "method": result["method"],
            "contamination": result["contamination"],
            "row_count": result["row_count"],
            "scored_rows": result["scored_rows"],
            "deduplicated_rows": result["deduplicated_rows"],
            "imputation": "missing values filled with each column's median before fitting",
            "feature_columns": result["feature_columns"],
            "excluded_columns": result["excluded_columns"],
            "anomaly_count": result["anomaly_count"],
            "anomaly_percentage": result["anomaly_percentage"],
            "breakdown": result.get("breakdown", {}),
        }

    # -- dispatch ----------------------------------------------------------
    def execute(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        handler = self._handlers.get(name)
        if handler is None:
            return {"error": f"Unknown tool '{name}'."}, f"Unknown tool '{name}'."
        try:
            return _json_safe(handler(arguments)), None
        except (ValueError, db.DatabaseError, analytics.DatasetError) as exc:
            logger.warning("Tool %s rejected the request: %s", name, exc)
            return {"error": str(exc)}, str(exc)
        except Exception as exc:  # pragma: no cover - upstream/network failure
            logger.exception("Tool %s failed", name)
            return {"error": f"Tool '{name}' failed: {exc}"}, str(exc)


def _build_user_prompt(goal: str, dataset_df: Any | None, document_id: str | None) -> str:
    context: list[str] = [f"Goal:\n{goal.strip()}"]
    if dataset_df is not None:
        context.append(
            f"An active dataset is attached ({dataset_df.shape[0]} rows x "
            f"{dataset_df.shape[1]} columns). Use describe_data / detect_anomalies "
            "to inspect it."
        )
    else:
        context.append("No dataset is attached to this run.")
    if document_id:
        context.append(f"The paper search is scoped to document_id={document_id}.")
    else:
        context.append("Paper search covers all of the user's documents.")
    context.append("Gather what you need with tools, then write the final Markdown report.")
    return "\n\n".join(context)


def _extract_title(goal: str) -> str:
    cleaned = re.sub(r"\s+", " ", goal).strip()
    if not cleaned:
        return "InsightForge analysis"
    return _truncate(cleaned, 120)


def run_agent_workflow(
    user_id: str,
    goal: str,
    dataset_df: Any | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Run the tool-calling loop and return the trace plus a Markdown report.

    Returns a dictionary with ``status`` (``completed`` or ``max_iterations``),
    ``steps`` (one entry per executed tool call), ``report`` (Markdown) and
    ``iterations`` (LLM turns used).
    """
    if not user_id:
        raise AgentError("user_id is required.")
    if not goal or not goal.strip():
        raise ValueError("goal cannot be empty.")

    client = get_groq_client()
    session = _ToolSession(user_id=user_id, dataset_df=dataset_df, document_id=document_id)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(goal, dataset_df, document_id)},
    ]

    steps: list[dict[str, Any]] = []
    final_text = ""
    iterations_used = 0
    status = "completed"

    for iteration in range(1, MAX_ITERATIONS + 1):
        iterations_used = iteration
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=MAX_AGENT_TOKENS,
            )
        except Exception as exc:
            raise AgentError(f"Groq request failed: {exc}") from exc

        message = completion.choices[0].message
        tool_calls = list(getattr(message, "tool_calls", None) or [])

        assistant_entry: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }
        if tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments or "{}",
                    },
                }
                for call in tool_calls
            ]
        messages.append(assistant_entry)

        if not tool_calls:
            final_text = (message.content or "").strip()
            break

        for call in tool_calls:
            name = call.function.name
            arguments, argument_error = _parse_arguments(call.function.arguments)
            if argument_error:
                result, error = {"error": argument_error}, argument_error
            else:
                result, error = session.execute(name, arguments)

            steps.append(
                {
                    "iteration": iteration,
                    "tool": name,
                    "arguments": analytics.sanitize(arguments),
                    "result": result,
                    "error": error,
                }
            )

            payload = json.dumps(result, default=analytics.sanitize, allow_nan=False)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": _truncate(payload, MAX_TOOL_RESULT_CHARS),
                }
            )
    else:
        # Every iteration asked for tools: force a synthesis with no more tools.
        status = "max_iterations"
        messages.append(
            {
                "role": "user",
                "content": (
                    "You have reached the tool-call limit. Using the information already "
                    "gathered, write the final Markdown report now. Do not request more tools."
                ),
            }
        )
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.1,
                max_tokens=MAX_FINAL_TOKENS,
            )
            final_text = (completion.choices[0].message.content or "").strip()
        except Exception as exc:
            raise AgentError(f"Groq final synthesis failed: {exc}") from exc

    if not final_text:
        if steps:
            final_text = (
                "## Summary\n"
                "The agent gathered tool results but did not produce a written synthesis.\n\n"
                "## Key findings\n"
                + "\n".join(
                    f"- `{step['tool']}` returned: "
                    f"{_truncate(json.dumps(step['result'], default=str), 300)}"
                    for step in steps
                )
                + "\n\n## Limitations\n"
                "The language model returned an empty response."
            )
        else:
            final_text = (
                "## Summary\n"
                "No analysis could be produced for this request.\n\n"
                "## Limitations\n"
                "The agent did not call any tools and returned no content."
            )

    return {
        "status": status,
        "iterations": iterations_used,
        "steps": steps,
        "report": final_text,
        "title": _extract_title(goal),
    }


__all__ = [
    "AgentError",
    "MAX_ITERATIONS",
    "MODEL_NAME",
    "SYSTEM_PROMPT",
    "TOOLS",
    "get_groq_client",
    "run_agent_workflow",
]
