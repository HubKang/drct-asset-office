from backend.app.schemas.trade_training_schema import RiskOrderPreviewRequest
from backend.app.services.trade_training_service import TradeTrainingService


class PreviewRepo:
    def __init__(self, budget: float = 2000):
        self.session = {
            "id": 1,
            "training_account_id": 7,
            "status": "진행중",
            "position_qty": 100,
            "avg_price": 100,
            "current_index": 0,
            "options_json": '{"fee_rate": 0.001}',
        }
        self.scenario = {"id": 10, "status": "ACTIVE", "stop_price": 90, "risk_budget_amount": budget}
        self.step = {
            "id": 11,
            "risk_scenario_id": 10,
            "plan_group": "BUY",
            "plan_type": "ENTRY",
            "step_no": 2,
            "status": "PLANNED",
            "trigger_price": 100,
        }

    def get_session(self, session_id):
        return self.session

    def get_active_risk_scenario(self, session_id):
        return self.scenario

    def get_current_risk_scenario(self, session_id):
        return self.scenario

    def get_latest_risk_scenario_revision(self, scenario_id):
        return {"id": 3}

    def get_risk_plan_step(self, step_id):
        steps = getattr(self, "steps", [self.step])
        return next((step for step in steps if int(step.get("id") or 0) == step_id), None)

    def list_risk_plan_steps(self, scenario_id):
        return getattr(self, "steps", [self.step])


def build_service(budget: float = 2000) -> TradeTrainingService:
    service = object.__new__(TradeTrainingService)
    service.repo = PreviewRepo(budget)
    service.db = None
    service._current_price_row = lambda session: {"close": 100}
    return service


def test_buy_preview_normal_caution_warning_boundaries():
    normal = build_service(2000).calculate_risk_order_preview(1, RiskOrderPreviewRequest(side="BUY", price=100, quantity=10, risk_plan_step_id=11))
    caution = build_service(1200).calculate_risk_order_preview(1, RiskOrderPreviewRequest(side="BUY", price=100, quantity=10, risk_plan_step_id=11))
    warning = build_service(1000).calculate_risk_order_preview(1, RiskOrderPreviewRequest(side="BUY", price=100, quantity=10, risk_plan_step_id=11))
    assert normal["severity"] == "INFO"
    assert caution["severity"] == "CAUTION"
    assert warning["severity"] == "WARNING"
    assert any(item["code"] == "RISK_BUDGET_EXCEEDED" for item in warning["warnings"])


def test_stop_area_buy_is_warning_without_blocking_preview():
    preview = build_service(100000).calculate_risk_order_preview(1, RiskOrderPreviewRequest(side="BUY", price=90, quantity=10, risk_plan_step_id=11))
    assert preview["severity"] == "WARNING"
    assert any(item["code"] == "STOP_AREA_BUY" for item in preview["warnings"])


def test_full_sell_projects_zero_risk():
    service = build_service(2000)
    service.repo.step = {**service.repo.step, "plan_group": "SELL", "plan_type": "TAKE_PROFIT"}
    preview = service.calculate_risk_order_preview(1, RiskOrderPreviewRequest(side="SELL", price=100, quantity=100, risk_plan_step_id=11))
    assert preview["projected_position"]["quantity"] == 0
    assert preview["projected_estimated_risk"] == 0
    assert preview["severity"] == "INFO"


def test_unplanned_order_is_caution_and_keeps_step_unselected():
    preview = build_service(100000).calculate_risk_order_preview(1, RiskOrderPreviewRequest(side="BUY", price=100, quantity=10, risk_plan_step_id=None))
    assert preview["selected_step"] is None
    assert preview["severity"] == "CAUTION"
    assert any(item["code"] == "UNPLANNED_BUY" for item in preview["warnings"])

def test_legacy_stop_steps_are_normalized_within_stop_group():
    service = build_service()
    normalized = service._normalize_sell_stop_types([
        {"id": 1, "plan_type": "TAKE_PROFIT", "trigger_price": 120, "step_no": 1},
        {"id": 2, "plan_type": "STOP_LOSS", "trigger_price": 90, "step_no": 2},
        {"id": 3, "plan_type": "STOP_LOSS", "trigger_price": 95, "step_no": 3},
    ])
    by_id = {step["id"]: step for step in normalized}
    assert by_id[1]["plan_type"] == "TAKE_PROFIT"
    assert by_id[2]["plan_type"] == "FULL_STOP"
    assert by_id[3]["plan_type"] == "PARTIAL_STOP"


def test_sell_preview_recommends_full_stop_below_full_stop_price():
    service = build_service(100000)
    service.repo.steps = [
        {"id": 21, "risk_scenario_id": 10, "plan_group": "SELL", "plan_type": "FULL_STOP", "step_no": 1, "status": "PLANNED", "trigger_price": 90},
        {"id": 22, "risk_scenario_id": 10, "plan_group": "SELL", "plan_type": "PARTIAL_STOP", "step_no": 2, "status": "PLANNED", "trigger_price": 95},
        {"id": 23, "risk_scenario_id": 10, "plan_group": "SELL", "plan_type": "TAKE_PROFIT", "step_no": 3, "status": "PLANNED", "trigger_price": 120},
    ]
    preview = service.calculate_risk_order_preview(1, RiskOrderPreviewRequest(side="SELL", price=89, quantity=40, risk_plan_step_id=None))
    assert preview["selected_step"]["id"] == 21
    assert any(item["code"] == "FULL_STOP_PARTIAL_QUANTITY" for item in preview["warnings"])


def test_partial_stop_full_quantity_is_warning_without_blocking():
    service = build_service(100000)
    service.repo.steps = [
        {"id": 21, "risk_scenario_id": 10, "plan_group": "SELL", "plan_type": "FULL_STOP", "step_no": 1, "status": "PLANNED", "trigger_price": 90},
        {"id": 22, "risk_scenario_id": 10, "plan_group": "SELL", "plan_type": "PARTIAL_STOP", "step_no": 2, "status": "PLANNED", "trigger_price": 95},
    ]
    preview = service.calculate_risk_order_preview(1, RiskOrderPreviewRequest(side="SELL", price=95, quantity=100, risk_plan_step_id=22))
    assert preview["selected_step"]["id"] == 22
    assert preview["projected_position"]["quantity"] == 0
    assert any(item["code"] == "PARTIAL_STOP_FULL_QUANTITY" for item in preview["warnings"])
