from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.drct_current_pattern_scan_schema import (
    MarkerCurrentPatternDetailResponse,
    MarkerCurrentPatternScanRequest,
    MarkerCurrentPatternSummaryResponse,
    MarkerPolicyValidationResponse,
    PatternDiscriminationDiagnostics,
)
from backend.app.schemas.drct_stock_signal_schema import (
    DrctSignalMarkerLinksPut,
    DrctSignalSearchCreate,
    DrctSignalSearchDetail,
    DrctSignalSearchListItem,
    DrctSignalSearchPatch,
    DrctSignalVersionCreate,
    DrctSignalVersionResponse,
    DrctRuleDiagnoseRequest,
    DrctRuleDiagnoseResponse,
    DrctRulePreviewRequest,
    DrctRulePreviewResponse,
    DrctRuleValidationResponse,
    DrctRuleVersionCreate,
    DrctHtsImportRequest,
    DrctHtsImportResponse,
    DrctStructuredRule,
    MarkerLinkResponse,
    MarkerOptionsResponse,
    TrainingSummary,
)
from backend.app.services.drct_stock_signal_service import DrctStockSignalService
from backend.app.services.drct_rule_engine import DrctRuleValidator
from backend.app.services.drct_rule_scan_service import DrctRuleScanService
from backend.app.services.drct_rule_service import DrctRuleService
from backend.app.services.drct_hts_import_service import DrctHtsImportService
from backend.app.schemas.drct_training_schema import (
    BaselineEvaluateResponse,
    TrainingCaseDetailResponse,
    TrainingCaseListResponse,
    TrainingDatasetRequest,
    TrainingReadinessResponse,
    TrainingOverviewResponse,
    RuleMismatchSummaryResponse,
    ValidationReportResponse,
)
from backend.app.services.drct_training_dataset_service import DrctTrainingDatasetService
from backend.app.services.drct_signal_validation_service import DrctSignalValidationService
from backend.app.schemas.drct_marker_learning_schema import (
    MarkerLearningCatalogResponse,
    MarkerLearningCaseDetailResponse,
    MarkerLearningCasesResponse,
    MarkerLearningOutcomesResponse,
    MarkerLearningReadinessResponse,
    MarkerRelatedSearchesResponse,
    MarkerPatternSignatureResponse,
    MarkerSimilarityCaseDetailResponse,
    MarkerSimilarityValidationRequest,
    MarkerSimilarityValidationResponse,
    MarkerAutoLearningSummaryResponse,
    MarkerLearningReviewCasesResponse,
    MarkerLearningReviewCaseDetail,
    MarkerLearningDecisionPut,
    MarkerLearningDecisionResponse,
)
from backend.app.services.marker_training_case_service import MarkerTrainingCaseService
from backend.app.services.marker_pattern_signature_service import MarkerPatternSignatureService
from backend.app.services.marker_auto_learning_service import MarkerAutoLearningService
from backend.app.services.marker_current_pattern_scan_service import MarkerCurrentPatternScanService
from backend.app.services.marker_candidate_policy_validation_service import MarkerCandidatePolicyValidationService


router = APIRouter(prefix="/drct-stock-signals", tags=["drct-stock-signals"])


@router.post("/marker-signals/scan", response_model=MarkerCurrentPatternSummaryResponse)
def marker_current_pattern_scan(
    payload: MarkerCurrentPatternScanRequest, db: Session = Depends(get_db),
):
    return MarkerCurrentPatternScanService(db).scan_summary(payload.analysis_date)


@router.post("/marker-signals/diagnostics", response_model=PatternDiscriminationDiagnostics)
def marker_current_pattern_diagnostics(
    payload: MarkerCurrentPatternScanRequest, db: Session = Depends(get_db),
):
    return MarkerCurrentPatternScanService(db).diagnostics(payload.analysis_date)


@router.post(
    "/marker-signals/diagnostics/{marker_id}/validation",
    response_model=MarkerPolicyValidationResponse,
)
def marker_candidate_policy_validation(
    marker_id: int, payload: MarkerCurrentPatternScanRequest, db: Session = Depends(get_db),
):
    return MarkerCandidatePolicyValidationService(db).validate(marker_id, payload.analysis_date)


@router.get("/marker-signals/{stock_id}/{marker_id}/detail", response_model=MarkerCurrentPatternDetailResponse)
def marker_current_pattern_detail(
    stock_id: int, marker_id: int, analysis_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return MarkerCurrentPatternScanService(db).detail(stock_id, marker_id, analysis_date)


@router.get("/marker-learning/markers", response_model=MarkerLearningCatalogResponse)
def marker_learning_markers(db: Session = Depends(get_db)):
    return MarkerAutoLearningService(db).catalog()


@router.get("/marker-learning/{marker_id}/summary", response_model=MarkerAutoLearningSummaryResponse)
def marker_auto_learning_summary(marker_id: int, db: Session = Depends(get_db)):
    return MarkerAutoLearningService(db).summary(marker_id)


@router.get("/marker-learning/{marker_id}/review-cases", response_model=MarkerLearningReviewCasesResponse)
def marker_learning_review_cases(marker_id: int, db: Session = Depends(get_db)):
    return MarkerAutoLearningService(db).review_cases(marker_id)


@router.get("/marker-learning/{marker_id}/review-cases/{event_id}", response_model=MarkerLearningReviewCaseDetail)
def marker_learning_review_case(marker_id: int, event_id: int, db: Session = Depends(get_db)):
    return MarkerAutoLearningService(db).review_case(marker_id, event_id)


@router.put("/marker-learning/{marker_id}/review-cases/{event_id}/decision", response_model=MarkerLearningDecisionResponse)
def marker_learning_review_decision(
    marker_id: int, event_id: int, payload: MarkerLearningDecisionPut, db: Session = Depends(get_db),
):
    return MarkerAutoLearningService(db).decide(marker_id, event_id, payload.decision, payload.decision_reason)


@router.get("/marker-learning/{marker_id}/readiness", response_model=MarkerLearningReadinessResponse)
def marker_learning_readiness(marker_id: int, db: Session = Depends(get_db)):
    return MarkerTrainingCaseService(db).readiness(marker_id)


@router.post("/marker-learning/{marker_id}/dataset-preview", response_model=MarkerLearningReadinessResponse)
def marker_learning_dataset_preview(marker_id: int, db: Session = Depends(get_db)):
    return MarkerTrainingCaseService(db).readiness(marker_id)


@router.get("/marker-learning/{marker_id}/cases", response_model=MarkerLearningCasesResponse)
def marker_learning_cases(
    marker_id: int, review_result: str = Query(default="ALL", pattern="^(ALL|S|F|UNDECIDED)$"),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return MarkerTrainingCaseService(db).cases(marker_id, review_result, page, page_size)


@router.get("/marker-learning/{marker_id}/cases/{event_id}", response_model=MarkerLearningCaseDetailResponse)
def marker_learning_case_detail(marker_id: int, event_id: int, db: Session = Depends(get_db)):
    return MarkerTrainingCaseService(db).case_detail(marker_id, event_id)


@router.get("/marker-learning/{marker_id}/outcomes", response_model=MarkerLearningOutcomesResponse)
def marker_learning_outcomes(marker_id: int, db: Session = Depends(get_db)):
    return MarkerTrainingCaseService(db).outcomes(marker_id)


@router.get("/marker-learning/{marker_id}/related-searches", response_model=MarkerRelatedSearchesResponse)
def marker_learning_related_searches(marker_id: int, db: Session = Depends(get_db)):
    return MarkerTrainingCaseService(db).related_searches(marker_id)


@router.get("/marker-learning/{marker_id}/pattern-signature", response_model=MarkerPatternSignatureResponse)
def marker_pattern_signature(
    marker_id: int, feature_profile: str = Query(default="CORE", pattern="^(CORE|ENRICHED)$"),
    db: Session = Depends(get_db),
):
    build = MarkerTrainingCaseService(db).build(marker_id)
    return MarkerPatternSignatureService.signature_response(build, feature_profile)  # type: ignore[arg-type]


@router.post("/marker-learning/{marker_id}/similarity-validation", response_model=MarkerSimilarityValidationResponse)
def marker_similarity_validation(
    marker_id: int, payload: MarkerSimilarityValidationRequest, db: Session = Depends(get_db),
):
    build = MarkerTrainingCaseService(db).build(marker_id)
    return MarkerPatternSignatureService.validation_response(build, payload.feature_profile)


@router.get("/marker-learning/{marker_id}/similarity-cases/{event_id}", response_model=MarkerSimilarityCaseDetailResponse)
def marker_similarity_case_detail(
    marker_id: int, event_id: int,
    feature_profile: str = Query(default="CORE", pattern="^(CORE|ENRICHED)$"),
    db: Session = Depends(get_db),
):
    build = MarkerTrainingCaseService(db).build(marker_id)
    result = MarkerPatternSignatureService.case_detail(build, event_id, feature_profile)  # type: ignore[arg-type]
    if result is None:
        raise HTTPException(404, "유사도 상세를 계산할 수 있는 Marker 사례가 아닙니다.")
    return result


@router.get("/searches", response_model=list[DrctSignalSearchListItem])
def list_searches(include_inactive: bool = Query(default=True), db: Session = Depends(get_db)):
    return DrctStockSignalService(db).list_searches(include_inactive)


@router.get("/searches/training-overview", response_model=TrainingOverviewResponse)
def training_overview(db: Session = Depends(get_db)):
    return DrctSignalValidationService(db).overview()


@router.get("/searches/{search_id}", response_model=DrctSignalSearchDetail)
def get_search(search_id: int, db: Session = Depends(get_db)):
    return DrctStockSignalService(db).get_search(search_id)


@router.post("/searches", response_model=DrctSignalSearchDetail, status_code=status.HTTP_201_CREATED)
def create_search(payload: DrctSignalSearchCreate, db: Session = Depends(get_db)):
    return DrctStockSignalService(db).create_search(payload)


@router.patch("/searches/{search_id}", response_model=DrctSignalSearchDetail)
def update_search(search_id: int, payload: DrctSignalSearchPatch, db: Session = Depends(get_db)):
    return DrctStockSignalService(db).update_search(search_id, payload)


@router.get("/searches/{search_id}/versions", response_model=list[DrctSignalVersionResponse])
def list_versions(search_id: int, db: Session = Depends(get_db)):
    return DrctStockSignalService(db).list_versions(search_id)


@router.post("/searches/{search_id}/versions", response_model=DrctSignalVersionResponse, status_code=status.HTTP_201_CREATED)
def create_version(search_id: int, payload: DrctSignalVersionCreate, db: Session = Depends(get_db)):
    return DrctStockSignalService(db).create_version(search_id, payload)


@router.put("/searches/{search_id}/marker-links", response_model=list[MarkerLinkResponse])
def replace_marker_links(search_id: int, payload: DrctSignalMarkerLinksPut, db: Session = Depends(get_db)):
    return DrctStockSignalService(db).replace_marker_links(search_id, payload)


@router.get("/marker-options", response_model=MarkerOptionsResponse)
def marker_options(db: Session = Depends(get_db)):
    return DrctStockSignalService(db).marker_options()


@router.get("/searches/{search_id}/training-summary", response_model=TrainingSummary)
def training_summary(search_id: int, db: Session = Depends(get_db)):
    return DrctStockSignalService(db).training_summary(search_id)


@router.get("/rule-capabilities")
def rule_capabilities():
    return DrctRuleValidator.capabilities()


@router.post("/rules/validate", response_model=DrctRuleValidationResponse)
def validate_rule(payload: DrctStructuredRule):
    return DrctRuleService.validate(payload)


@router.post("/rules/import-hts", response_model=DrctHtsImportResponse)
def import_hts_rule(payload: DrctHtsImportRequest):
    """Deterministic, transient HTS-to-DrCT conversion preview."""
    return DrctHtsImportService().parse(payload.text, payload.expression, payload.resolutions)


@router.post("/searches/{search_id}/rule-versions", response_model=DrctSignalVersionResponse, status_code=status.HTTP_201_CREATED)
def create_rule_version(search_id: int, payload: DrctRuleVersionCreate, db: Session = Depends(get_db)):
    return DrctRuleService(db).create_rule_version(search_id, payload)


@router.post("/searches/{search_id}/rule-preview", response_model=DrctRulePreviewResponse)
def rule_preview(search_id: int, payload: DrctRulePreviewRequest, db: Session = Depends(get_db)):
    return DrctRuleScanService(db).preview(search_id, payload.analysis_date, payload.include_all)


@router.post("/searches/{search_id}/rule-diagnose", response_model=DrctRuleDiagnoseResponse)
def rule_diagnose(search_id: int, payload: DrctRuleDiagnoseRequest, db: Session = Depends(get_db)):
    return DrctRuleScanService(db).diagnose(search_id, payload.stock_id, payload.analysis_date)


@router.get("/searches/{search_id}/training-readiness", response_model=TrainingReadinessResponse)
def training_readiness(search_id: int, search_version_id: int | None = Query(default=None, gt=0), db: Session = Depends(get_db)):
    return DrctTrainingDatasetService(db).readiness(search_id, search_version_id)


@router.post("/searches/{search_id}/training-dataset-preview", response_model=TrainingReadinessResponse)
def training_dataset_preview(search_id: int, payload: TrainingDatasetRequest, db: Session = Depends(get_db)):
    return DrctTrainingDatasetService(db).preview(search_id, payload.search_version_id)


@router.get("/searches/{search_id}/training-cases", response_model=TrainingCaseListResponse)
def training_cases(
    search_id: int,
    search_version_id: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    include_all: bool = Query(default=False),
    rule_status: str | None = Query(default=None),
    condition_code: str | None = Query(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]*$"),
    label: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return DrctTrainingDatasetService(db).cases(search_id, search_version_id, page, page_size, include_all, rule_status, condition_code, label)


@router.get("/searches/{search_id}/rule-mismatch-summary", response_model=RuleMismatchSummaryResponse)
def rule_mismatch_summary(search_id: int, search_version_id: int | None = Query(default=None, gt=0), db: Session = Depends(get_db)):
    return DrctTrainingDatasetService(db).mismatch_summary(search_id, search_version_id)


@router.get("/searches/{search_id}/training-cases/{stock_id}/{d0}", response_model=TrainingCaseDetailResponse)
def training_case_detail(
    search_id: int, stock_id: int, d0: str,
    search_version_id: int | None = Query(default=None, gt=0), db: Session = Depends(get_db),
):
    return DrctTrainingDatasetService(db).case_detail(search_id, stock_id, d0, search_version_id)


@router.post("/searches/{search_id}/baseline-evaluate", response_model=BaselineEvaluateResponse)
def baseline_evaluate(search_id: int, payload: TrainingDatasetRequest, db: Session = Depends(get_db)):
    return DrctTrainingDatasetService(db).baseline(search_id, payload.search_version_id, payload.feature_profile)


@router.post("/searches/{search_id}/validation-report", response_model=ValidationReportResponse)
def validation_report(search_id: int, payload: TrainingDatasetRequest, db: Session = Depends(get_db)):
    return DrctSignalValidationService(db).report(search_id, payload.search_version_id, payload.feature_profile)
