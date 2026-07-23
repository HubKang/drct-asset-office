from __future__ import annotations

from typing import Any


VALIDATION_SUMMARY_SCHEMA_VERSION = 1

# Validation runs may return detailed samples for immediate inspection, but only
# aggregate metrics in this allow-list are durable application data.
_DURABLE_AGGREGATE_FIELDS = (
    "signal_id",
    "sample_count",
    "triggered_count",
    "confirmed_count",
    "confirmation_rate",
    "occurrence_count",
    "false_start_count",
    "opposing_count",
    "invalidation_count",
    "release_count",
    "average_confirmation_periods",
    "average_persistence",
    "median_persistence",
    "max_persistence",
    "average_score",
    "median_score",
    "active_ratio",
    "data_insufficient_count",
    "required_satisfaction_count",
    "confirm_contribution_count",
    "opposing_penalty_count",
    "state_counts",
    "condition_pass_counts",
    "condition_contributions",
    "variant_summaries",
    "warnings",
)


def compact_validation_summary(summary: Any) -> dict[str, Any]:
    """Return the durable, aggregate-only portion of a validation result."""
    if not isinstance(summary, dict) or not summary:
        return {}

    compact: dict[str, Any] = {
        "summary_schema_version": VALIDATION_SUMMARY_SCHEMA_VERSION,
    }
    for field in _DURABLE_AGGREGATE_FIELDS:
        if field in summary:
            compact[field] = summary[field]
    return compact
