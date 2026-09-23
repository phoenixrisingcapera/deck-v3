"""Deterministic illustrative finance calculations with assumption lineage."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.services.ai_vc.models import CalculationNode, EvidenceClass


class FinancialAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    value: float
    unit: str
    evidence_class: EvidenceClass
    source_evidence_ids: list[str] = Field(default_factory=list)
    confidence: str = "unknown"


def _value(assumptions: dict[str, FinancialAssumption], name: str) -> Decimal:
    if name not in assumptions:
        raise ValueError(f"Missing financial assumption: {name}")
    return Decimal(str(assumptions[name].value))


def calculate_saas_scenario(values: list[FinancialAssumption]) -> dict:
    assumptions = {item.name: item for item in values}
    accounts = _value(assumptions, "accounts")
    monthly_price = _value(assumptions, "monthly_price")
    annual_revenue = accounts * monthly_price * Decimal(12)
    calculations = [CalculationNode(
        id="calc_arr", formula="accounts * monthly_price * 12", value=float(annual_revenue),
        unit=assumptions["monthly_price"].unit + "/year",
        assumption_ids=[assumptions["accounts"].id, assumptions["monthly_price"].id],
    )]
    if "gross_margin" in assumptions:
        gross_profit = annual_revenue * _value(assumptions, "gross_margin")
        calculations.append(CalculationNode(
            id="calc_gross_profit", formula="ARR * gross_margin", value=float(gross_profit),
            unit=assumptions["monthly_price"].unit + "/year",
            assumption_ids=[assumptions["gross_margin"].id], calculation_ids=["calc_arr"],
        ))
    return {
        "schemaVersion": "ai-vc-financial-model.v1", "family": "saas",
        "presentationLabel": "Illustrative scenario",
        "assumptions": [item.model_dump() for item in values],
        "calculations": [item.model_dump() for item in calculations],
        "policy": "Application-calculated; not company guidance unless assumptions are MANAGEMENT_PROJECTION.",
    }
