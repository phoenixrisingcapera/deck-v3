from __future__ import annotations

from typing import Any


def build_critique_decision(
    *,
    warnings: list[str],
    missing_inputs: list[Any],
    unsupported_fact_ids: list[str] | None = None,
    unsupported_facts: list[str] | None = None,
    cited_safety_flags: list[str] | None = None,
    sensitive_claim_strengthened: bool = False,
    unchanged_output: bool = False,
    missing_required_source_fact_id: bool = False,
) -> dict[str, Any]:
    dimensions = []
    repair_actions = []
    unsupported_fact_ids = unsupported_fact_ids or []
    unsupported_facts = unsupported_facts or []
    cited_safety_flags = cited_safety_flags or []

    if unsupported_fact_ids or unsupported_facts or missing_required_source_fact_id:
        dimensions.append(_dimension("factuality", "blocking", "Output cites facts that are not in the approved source fact package."))
        repair_actions.append(
            _repair_action(
                "fix_source_fact_citations",
                "Replace unsupported citations with approved source fact IDs or move the claim into missing inputs.",
                "factuality",
            )
        )
    elif any("source fact" in warning.lower() or "source_fact" in warning.lower() for warning in warnings):
        dimensions.append(_dimension("factuality", "warning", "Output has incomplete source fact citation coverage."))
        repair_actions.append(
            _repair_action(
                "add_source_fact_citations",
                "Add approved source fact IDs and readable source labels for every factual claim.",
                "factuality",
            )
        )

    if missing_inputs:
        dimensions.append(_dimension("evidence", "warning", "Output declares missing evidence that needs user or source confirmation."))
        repair_actions.append(
            _repair_action(
                "surface_missing_evidence",
                "Keep the output conservative and preserve missing evidence in the missing-input fields.",
                "evidence",
            )
        )

    if sensitive_claim_strengthened:
        dimensions.append(_dimension("claim_safety", "blocking", "Output strengthens a sensitive source claim."))
        repair_actions.append(
            _repair_action(
                "downgrade_sensitive_claim",
                "Remove unsupported metrics or strengthening language and preserve only the cited source claim.",
                "claim_safety",
            )
        )
    elif "requires_user_confirmation" in cited_safety_flags:
        dimensions.append(
            _dimension(
                "claim_safety",
                "info",
                "Output cites a user-supplied financial or regulatory fact that should not be strengthened.",
            )
        )
    elif "do_not_strengthen" in cited_safety_flags:
        dimensions.append(_dimension("claim_safety", "info", "Output cites facts that should not be strengthened."))

    if unchanged_output:
        dimensions.append(_dimension("edit_quality", "warning", "The generated edit did not materially change the source text."))
        repair_actions.append(
            _repair_action(
                "make_reviewable_change",
                "Make a focused rewrite that satisfies the instruction while preserving source-backed facts.",
                "edit_quality",
            )
        )

    if any("confidence" in warning.lower() for warning in warnings):
        dimensions.append(_dimension("confidence", "warning", "Confidence metadata needs review."))

    if not dimensions and warnings:
        dimensions.append(_dimension("general", "warning", "Output has critique warnings that should be reviewed."))
    if not dimensions:
        dimensions.append(_dimension("overall", "info", "No critique issues detected."))

    blocking_count = sum(1 for dimension in dimensions if dimension["severity"] == "blocking")
    warning_count = sum(1 for dimension in dimensions if dimension["severity"] == "warning")
    return {
        "schemaVersion": "critique-decision.v1",
        "status": "blocking" if blocking_count else "review" if warning_count or missing_inputs else "passed",
        "blockingCount": blocking_count,
        "warningCount": warning_count,
        "dimensions": dimensions,
        "repairActions": repair_actions,
        "reasonCodes": sorted(
            {
                *({"unsupported_source_fact_id"} if unsupported_fact_ids else set()),
                *({"unmatched_source_fact_label"} if unsupported_facts else set()),
                *({"missing_required_source_fact_id"} if missing_required_source_fact_id else set()),
                *({"unsafe_fact_strengthening"} if sensitive_claim_strengthened else set()),
            }
        ),
    }


def summarize_critique_decisions(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    blocking_count = sum(int(decision.get("blockingCount") or 0) for decision in decisions)
    warning_count = sum(int(decision.get("warningCount") or 0) for decision in decisions)
    repair_actions = [
        action
        for decision in decisions
        for action in (decision.get("repairActions") or [])
        if isinstance(action, dict)
    ]
    return {
        "schemaVersion": "critique-summary.v1",
        "status": "blocking" if blocking_count else "review" if warning_count else "passed",
        "blockingCount": blocking_count,
        "warningCount": warning_count,
        "repairActions": repair_actions[:25],
        "reasonCodes": sorted(
            {
                str(reason_code)
                for decision in decisions
                for reason_code in (decision.get("reasonCodes") or [])
                if str(reason_code).strip()
            }
        ),
    }


def _dimension(name: str, severity: str, message: str) -> dict[str, str]:
    return {"name": name, "severity": severity, "message": message}


def _repair_action(action_type: str, instruction: str, dimension: str) -> dict[str, str]:
    return {
        "type": action_type,
        "dimension": dimension,
        "instruction": instruction,
    }
