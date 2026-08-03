from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_signal_schema import (
    MarketSignalDefinition,
    MarketSignalDefinitionListResponse,
    MarketSignalConditionPreviewRequest,
    MarketSignalConditionPreviewResponse,
    MarketSignalCurrentEvaluateRequest,
    MarketSignalEvaluateRequest,
    MarketSignalEvaluateResponse,
    MarketSignalEventListResponse,
    MarketSignalGptDraftRequest,
    MarketSignalGptDraftResponse,
    MarketSignalGenericActionRequest,
    MarketSignalGenericItemResponse,
    MarketSignalGenericListResponse,
    MarketSignalIndicatorCatalogResponse,
    MarketSignalSimulationResponse,
    MarketSignalUpsertRequest,
    MarketSignalUserReviewRequest,
)
from backend.app.services.market_signal_service import MarketSignalService

router = APIRouter()


@router.get("/market-signals", response_model=MarketSignalDefinitionListResponse)
def list_market_signals(status: str | None = Query(default=None), db: Session = Depends(get_db)) -> MarketSignalDefinitionListResponse:
    return MarketSignalService(db).list_signals(status_filter=status)


@router.post("/market-signals/evaluate", response_model=MarketSignalEvaluateResponse)
def evaluate_market_signals(payload: MarketSignalEvaluateRequest, db: Session = Depends(get_db)) -> MarketSignalEvaluateResponse:
    return MarketSignalService(db).evaluate(payload)


@router.get("/market-signals/events", response_model=MarketSignalEventListResponse)
def list_market_signal_events(limit: int = Query(default=50, ge=1, le=300), db: Session = Depends(get_db)) -> MarketSignalEventListResponse:
    return MarketSignalService(db).list_events(limit=limit)


@router.get("/market-signals/events/today", response_model=MarketSignalGenericItemResponse)
def list_today_market_signal_events(db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return {"item": MarketSignalService(db).list_events_today()}


@router.get("/market-signals/overview", response_model=dict)
def get_market_signal_overview(db: Session = Depends(get_db)) -> dict:
    return MarketSignalService(db).overview()


@router.post("/signal-evaluations/run-current", response_model=dict)
def run_current_market_signal_evaluations(
    payload: MarketSignalCurrentEvaluateRequest,
    db: Session = Depends(get_db),
) -> dict:
    return MarketSignalService(db).evaluate_current_signals(
        trigger_type=payload.trigger_type,
        force=payload.force,
    )


@router.get("/signal-evaluations/today-transitions", response_model=dict)
def list_today_current_market_signal_transitions(db: Session = Depends(get_db)) -> dict:
    return MarketSignalService(db).list_today_current_transitions()


@router.get("/signal-evaluations/current", response_model=dict)
def list_current_market_signal_states(db: Session = Depends(get_db)) -> dict:
    return MarketSignalService(db).list_current_signal_states()

@router.post("/market-signals/gpt-rule-draft", response_model=MarketSignalGptDraftResponse)
def draft_market_signal_with_gpt(payload: MarketSignalGptDraftRequest, db: Session = Depends(get_db)) -> MarketSignalGptDraftResponse:
    return MarketSignalService(db).gpt_rule_draft(payload)


@router.post("/market-signals/gpt-rule-design", response_model=MarketSignalGenericItemResponse)
def design_market_signal_with_gpt(payload: MarketSignalGptDraftRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).gpt_rule_design(payload)


@router.get("/market-signals/indicator-catalog", response_model=MarketSignalIndicatorCatalogResponse)
def list_market_signal_indicator_catalog(db: Session = Depends(get_db)) -> MarketSignalIndicatorCatalogResponse:
    return MarketSignalService(db).indicator_catalog()


@router.get("/market-signals/catalog", response_model=dict)
def list_market_signal_catalog(
    category: str | None = Query(default=None),
    country: str | None = Query(default=None),
    readiness: str | None = Query(default=None),
    signal_readiness: str | None = Query(default=None),
    profile_code: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return MarketSignalService(db).signal_catalog(
        category=category,
        country=country,
        readiness=readiness,
        signal_readiness=signal_readiness,
        profile_code=profile_code,
        search=search,
    )


@router.get("/market-signals/model-profiles", response_model=MarketSignalGenericListResponse)
def list_market_signal_model_profiles(db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_model_profiles()


@router.post("/market-signals/condition-preview", response_model=MarketSignalConditionPreviewResponse)
def preview_market_signal_condition(payload: MarketSignalConditionPreviewRequest, db: Session = Depends(get_db)) -> MarketSignalConditionPreviewResponse:
    return MarketSignalService(db).condition_preview(payload)


@router.get("/market-signals/single-indicator", response_model=MarketSignalGenericListResponse)
def list_single_indicator_signals(db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_single_indicator_signals()


@router.get("/market-signals/single-indicator/coverage-summary", response_model=MarketSignalGenericItemResponse)
def get_single_indicator_coverage_summary(db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).single_indicator_coverage_summary()


@router.post("/market-signals/single-indicator/preview", response_model=MarketSignalGenericItemResponse)
def preview_single_indicator_draft(payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).preview_single_indicator_draft(payload)


@router.post("/market-signals/single-indicator/create-draft", response_model=MarketSignalGenericItemResponse)
def create_single_indicator_draft(payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).create_single_indicator_draft(payload)


@router.post("/market-signals/single-indicator/create-drafts", response_model=dict)
def create_single_indicator_drafts(payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> dict:
    return MarketSignalService(db).create_single_indicator_drafts(payload)


@router.get("/market-signals/single-indicator/{model_id}", response_model=MarketSignalGenericItemResponse)
def get_single_indicator_signal(model_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).get_single_indicator_signal(model_id)


@router.post("/market-signals/single-indicator/{model_id}/evaluate", response_model=MarketSignalGenericItemResponse)
def evaluate_single_indicator_signal(model_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).evaluate_single_indicator(model_id, observation_date=payload.observation_date, save=payload.save)


@router.post("/market-signals/single-indicator/{model_id}/simulate", response_model=dict)
def simulate_single_indicator_signal(model_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> dict:
    return MarketSignalService(db).simulate_single_indicator(model_id, years=payload.years)


@router.get("/market-signals/single-indicator/{model_id}/trend-chart", response_model=dict)
def get_single_indicator_trend_chart(model_id: int, observation_date: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    return MarketSignalService(db).trend_chart(model_id, observation_date=observation_date)


@router.get("/market-signals/{signal_id}/evaluation-history", response_model=dict)
def get_market_signal_evaluation_history(
    signal_id: int,
    event_only: bool = Query(default=False),
    state: str | None = Query(default=None),
    evaluation_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=300),
    db: Session = Depends(get_db),
) -> dict:
    return MarketSignalService(db).evaluation_history(
        signal_id, event_only=event_only, state=state, evaluation_type=evaluation_type,
        date_from=date_from, date_to=date_to, page=page, page_size=page_size,
    )


@router.get("/market-signals/{signal_id}/evaluation-history/summary", response_model=dict)
def get_market_signal_evaluation_history_summary(signal_id: int, db: Session = Depends(get_db)) -> dict:
    return MarketSignalService(db).evaluation_history_summary(signal_id)


@router.post("/market-signals/{signal_id}/evaluate-now", response_model=MarketSignalGenericItemResponse)
def evaluate_market_signal_now(signal_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).evaluate_now(signal_id)


@router.post("/market-signals/{signal_id}/repair-baseline", response_model=MarketSignalGenericItemResponse)
def repair_market_signal_baseline(signal_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).repair_baseline(signal_id, apply=bool((payload.payload or {}).get("apply")))


@router.post("/market-signals/repair-baselines", response_model=MarketSignalGenericItemResponse)
def repair_active_market_signal_baselines(payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).repair_active_baselines(apply=bool((payload.payload or {}).get("apply")))


@router.post("/market-signals/{signal_id}/mark-validation-complete", response_model=MarketSignalGenericItemResponse)
def mark_market_signal_validation_complete(signal_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).mark_validation_complete(signal_id, payload)


@router.post("/market-signals/{signal_id}/activate-with-approval", response_model=MarketSignalGenericItemResponse)
def activate_market_signal_with_approval(signal_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).activate_with_approval(signal_id, payload)


@router.post("/market-signals/{signal_id}/deactivate-with-reason", response_model=MarketSignalGenericItemResponse)
def deactivate_market_signal_with_reason(signal_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).deactivate_with_reason(signal_id, payload)


@router.post("/market-signals/{signal_id}/clone-version", response_model=MarketSignalGenericItemResponse)
def clone_market_signal_version(signal_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).clone_signal_version(signal_id, payload)


@router.get("/market-signals/composite", response_model=MarketSignalGenericListResponse)
def list_composite_signals(db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_composite_signals()


@router.post("/market-signals/composite/audit", response_model=MarketSignalGenericItemResponse)
def audit_composite_signal_operations(payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).audit_composite_operations(apply=bool((payload.payload or {}).get("apply")))


@router.get("/market-signals/composite/{signal_id}", response_model=MarketSignalGenericItemResponse)
def get_composite_signal(signal_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).get_composite_signal(signal_id)


@router.post("/market-signals/composite/{signal_id}/evaluate", response_model=MarketSignalGenericItemResponse)
def evaluate_composite_signal(signal_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).evaluate_composite(signal_id, observation_date=payload.observation_date, save=payload.save)


@router.post("/market-signals/composite/{signal_id}/simulate", response_model=dict)
def simulate_composite_signal(signal_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> dict:
    return MarketSignalService(db).simulate_composite(signal_id, years=payload.years)


@router.post("/market-signals/composite/templates/{template_id}/validate-readiness", response_model=MarketSignalGenericItemResponse)
def validate_composite_template_readiness(template_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).validate_composite_template_readiness(template_id)


@router.get("/market-signals/phenomena", response_model=MarketSignalGenericListResponse)
def list_objective_phenomena(
    grade: str | None = Query(default=None),
    state: str | None = Query(default=None),
    category: str | None = Query(default=None),
    flow_candidate: bool | None = Query(default=None),
    source_status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_phenomena(
        grade=grade,
        state=state,
        category=category,
        flow_candidate=flow_candidate,
        source_status=source_status,
        search=search,
    )


@router.get("/market-signals/phenomena/overview", response_model=MarketSignalGenericListResponse)
def objective_phenomena_overview(db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_phenomena()


@router.post("/market-signals/phenomena/repair", response_model=MarketSignalGenericItemResponse)
def repair_objective_phenomena(payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).repair_objective_phenomena(apply=bool((payload.payload or {}).get("apply", False)))


@router.get("/market-signals/phenomena/{phenomenon_id}", response_model=MarketSignalGenericItemResponse)
def get_objective_phenomenon(phenomenon_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).get_phenomenon(phenomenon_id)


@router.patch("/market-signals/phenomena/{phenomenon_id}", response_model=MarketSignalGenericItemResponse)
def update_objective_phenomenon(phenomenon_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).update_phenomenon(phenomenon_id, payload)


@router.post("/market-signals/phenomena/{phenomenon_id}/evaluate", response_model=MarketSignalGenericItemResponse)
def evaluate_objective_phenomenon(phenomenon_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).evaluate_phenomenon(phenomenon_id, observation_date=payload.observation_date, save=payload.save)


@router.post("/market-signals/phenomena/{phenomenon_id}/evaluate-now", response_model=MarketSignalGenericItemResponse)
def evaluate_objective_phenomenon_now(phenomenon_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).evaluate_phenomenon(phenomenon_id, observation_date=payload.observation_date, save=True)


@router.get("/market-signals/phenomena/{phenomenon_id}/episodes", response_model=MarketSignalGenericListResponse)
@router.get("/market-signals/phenomena/{phenomenon_id}/evaluation-history", response_model=MarketSignalGenericListResponse)
def list_objective_phenomenon_episodes(phenomenon_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_phenomenon_evaluation_history(phenomenon_id)


@router.get("/market-signals/phenomena/{phenomenon_id}/evaluation-history/summary", response_model=MarketSignalGenericItemResponse)
def objective_phenomenon_history_summary(phenomenon_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).phenomenon_evaluation_history_summary(phenomenon_id)


@router.post("/market-signals/phenomena/{phenomenon_id}/flow-candidate", response_model=MarketSignalGenericItemResponse)
def add_objective_phenomenon_flow_candidate(phenomenon_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).add_phenomenon_flow_candidate(phenomenon_id, payload)


@router.post("/market-signals/phenomena/{phenomenon_id}/flow-candidate/remove", response_model=MarketSignalGenericItemResponse)
def remove_objective_phenomenon_flow_candidate(phenomenon_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).remove_phenomenon_flow_candidate(phenomenon_id)


@router.get("/market-signals/phenomena/{phenomenon_id}/gpt-diagnosis-prompt", response_model=MarketSignalGenericItemResponse)
def get_objective_phenomenon_gpt_prompt(phenomenon_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).gpt_phenomenon_diagnosis(phenomenon_id, MarketSignalGenericActionRequest())


@router.post("/market-signals/phenomena/{phenomenon_id}/gpt-diagnosis", response_model=MarketSignalGenericItemResponse)
def diagnose_objective_phenomenon_with_gpt(phenomenon_id: int, payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericItemResponse:
    return MarketSignalService(db).gpt_phenomenon_diagnosis(phenomenon_id, payload)

@router.get("/market-signals/evidence-sources", response_model=MarketSignalGenericListResponse)
def list_market_signal_evidence_sources(db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_evidence_sources()


@router.post("/market-signals/evidence-sources", response_model=MarketSignalGenericListResponse)
def upsert_market_signal_evidence_source(payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).upsert_evidence_source(payload)


@router.get("/market-signals/rule-experiments", response_model=MarketSignalGenericListResponse)
def list_market_signal_rule_experiments(db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_rule_experiments()


@router.post("/market-signals/rule-experiments", response_model=MarketSignalGenericListResponse)
def create_market_signal_rule_experiment(payload: MarketSignalGenericActionRequest, db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).create_rule_experiment(payload)


@router.post("/market-signals/rule-experiments/{experiment_id}/approve", response_model=MarketSignalGenericListResponse)
def approve_market_signal_rule_experiment(experiment_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).set_rule_experiment_status(experiment_id, "APPROVED")


@router.post("/market-signals/rule-experiments/{experiment_id}/reject", response_model=MarketSignalGenericListResponse)
def reject_market_signal_rule_experiment(experiment_id: int, db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).set_rule_experiment_status(experiment_id, "REJECTED")


@router.get("/market-signals/rule-templates", response_model=MarketSignalGenericListResponse)
def list_market_signal_rule_templates(db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).list_rule_templates()


@router.post("/market-signals/rule-templates/{template_id}/copy", response_model=MarketSignalDefinition)
def copy_market_signal_rule_template(template_id: int, db: Session = Depends(get_db)) -> MarketSignalDefinition:
    return MarketSignalService(db).copy_template_to_draft(template_id)


@router.post("/market-signals/user-reviews", response_model=MarketSignalGenericListResponse)
def create_market_signal_user_review(payload: MarketSignalUserReviewRequest, db: Session = Depends(get_db)) -> MarketSignalGenericListResponse:
    return MarketSignalService(db).create_user_review(payload)


@router.get("/market-signals/{signal_id}", response_model=MarketSignalDefinition)
def get_market_signal(signal_id: int, db: Session = Depends(get_db)) -> MarketSignalDefinition:
    return MarketSignalService(db).get_signal(signal_id)


@router.post("/market-signals", response_model=MarketSignalDefinition)
def create_market_signal(payload: MarketSignalUpsertRequest, db: Session = Depends(get_db)) -> MarketSignalDefinition:
    return MarketSignalService(db).upsert_signal(payload)


@router.put("/market-signals/{signal_id}", response_model=MarketSignalDefinition)
def update_market_signal(signal_id: int, payload: MarketSignalUpsertRequest, db: Session = Depends(get_db)) -> MarketSignalDefinition:
    return MarketSignalService(db).upsert_signal(payload, signal_id=signal_id)


@router.post("/market-signals/{signal_id}/activate", response_model=MarketSignalDefinition)
def activate_market_signal(signal_id: int, db: Session = Depends(get_db)) -> MarketSignalDefinition:
    return MarketSignalService(db).set_status(signal_id, "ACTIVE")


@router.post("/market-signals/{signal_id}/deactivate", response_model=MarketSignalDefinition)
def deactivate_market_signal(signal_id: int, db: Session = Depends(get_db)) -> MarketSignalDefinition:
    return MarketSignalService(db).set_status(signal_id, "INACTIVE")


@router.post("/market-signals/{signal_id}/archive", response_model=MarketSignalDefinition)
def archive_market_signal(signal_id: int, db: Session = Depends(get_db)) -> MarketSignalDefinition:
    return MarketSignalService(db).set_status(signal_id, "ARCHIVED")


@router.get("/market-signals/{signal_id}/evaluations", response_model=MarketSignalEvaluateResponse)
def list_market_signal_evaluations(signal_id: int, limit: int = Query(default=50, ge=1, le=300), db: Session = Depends(get_db)) -> MarketSignalEvaluateResponse:
    return MarketSignalService(db).list_evaluations(signal_id, limit=limit)


@router.post("/market-signals/{signal_id}/simulate", response_model=MarketSignalSimulationResponse)
def simulate_market_signal(signal_id: int, years: int = Query(default=1, ge=1, le=5), db: Session = Depends(get_db)) -> MarketSignalSimulationResponse:
    return MarketSignalService(db).simulate(signal_id, years=years)
