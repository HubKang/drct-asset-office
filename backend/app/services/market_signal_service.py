from __future__ import annotations

import json
import math
import statistics
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session


SUPPORTED_TRANSFORMS = {
    "RAW_VALUE",
    "CHANGE",
    "CHANGE_RATE",
    "MOM",
    "YOY",
    "MOVING_AVERAGE",
    "MA_CROSS_UP",
    "MA_CROSS_DOWN",
    "SLOPE",
    "TREND_DIRECTION",
    "TURN_UP",
    "TURN_DOWN",
    "ACCELERATING_UP",
    "DECELERATING_UP",
    "ACCELERATING_DOWN",
    "DECELERATING_DOWN",
    "Z_SCORE",
    "PERCENTILE",
    "DISTANCE_FROM_MA",
    "N_PERIOD_HIGH",
    "N_PERIOD_LOW",
    "CONSECUTIVE_UP",
    "CONSECUTIVE_DOWN",
    "PERSISTENCE",
    "SPREAD",
    "RATIO",
    "RELATIVE_STRENGTH",
    "CORRELATION",
    "DIVERGENCE",
    "TREND_STATE",
    "REGRESSION_SLOPE",
    "NORMALIZED_SLOPE",
    "TREND_STRENGTH",
    "TREND_DURATION",
    "CHANNEL_POSITION",
    "TREND_BREAK_UP",
    "TREND_BREAK_DOWN",
    "BREAK_CONFIRMED_UP",
    "BREAK_CONFIRMED_DOWN",
    "FALSE_BREAK_UP",
    "FALSE_BREAK_DOWN",
    "REVERSAL_CONFIRMED_UP",
    "REVERSAL_CONFIRMED_DOWN",
    "TREND_RESUMED_UP",
    "TREND_RESUMED_DOWN",
}


class MarketSignalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_signals(self, *, status_filter: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        where = ""
        if status_filter:
            where = "WHERE status = :status"
            params["status"] = status_filter.upper()
        rows = self.db.execute(
            text(f"SELECT * FROM market_signal_definitions {where} ORDER BY updated_at DESC, id DESC"),
            params,
        ).mappings().all()
        return {"items": [self._definition_item(row, include_conditions=False) for row in rows]}

    def get_signal(self, signal_id: int) -> dict[str, Any]:
        row = self._definition_row(signal_id)
        return self._definition_item(row, include_conditions=True)

    def upsert_signal(self, payload: Any, *, signal_id: int | None = None) -> dict[str, Any]:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        conditions = data.pop("conditions", [])
        change_reason = data.pop("change_reason", None)
        if signal_id is None:
            row = self.db.execute(
                text(
                    """
                    INSERT INTO market_signal_definitions
                    (signal_code, signal_name, description, category, signal_type, horizon, status, interpretation_direction,
                     phenomenon_template, process_template, result_template, persistence_periods, cooldown_periods, minimum_data_quality)
                    VALUES (:signal_code, :signal_name, :description, :category, :signal_type, :horizon, :status, :interpretation_direction,
                            :phenomenon_template, :process_template, :result_template, :persistence_periods, :cooldown_periods, :minimum_data_quality)
                    RETURNING id
                    """
                ),
                self._definition_params(data),
            ).first()
            signal_id = int(row[0])
        else:
            self.db.execute(
                text(
                    """
                    UPDATE market_signal_definitions
                    SET signal_code = :signal_code,
                        signal_name = :signal_name,
                        description = :description,
                        category = :category,
                        signal_type = :signal_type,
                        horizon = :horizon,
                        status = :status,
                        interpretation_direction = :interpretation_direction,
                        phenomenon_template = :phenomenon_template,
                        process_template = :process_template,
                        result_template = :result_template,
                        persistence_periods = :persistence_periods,
                        cooldown_periods = :cooldown_periods,
                        minimum_data_quality = :minimum_data_quality,
                        current_version = current_version + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """
                ),
                {"id": signal_id, **self._definition_params(data)},
            )
            self.db.execute(text("DELETE FROM market_signal_conditions WHERE signal_definition_id = :id"), {"id": signal_id})
        for order, condition in enumerate(conditions, start=1):
            item = condition.model_dump() if hasattr(condition, "model_dump") else dict(condition)
            self._insert_condition(signal_id, item, order)
        self.db.commit()
        self._snapshot_version(signal_id, change_reason or "Rule saved")
        return self.get_signal(signal_id)

    def set_status(self, signal_id: int, status_value: str) -> dict[str, Any]:
        normalized = status_value.upper()
        if normalized == "ACTIVE":
            row = self._definition_row(signal_id)
            if str(row.get("validation_status") or "UNVALIDATED").upper() not in {"VALIDATED", "ACTIVATION_READY"} and not int(row.get("activation_ready") or 0):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="validation must be completed before activation")
            self.db.execute(
                text(
                    """
                    UPDATE market_signal_definitions
                    SET status = 'ACTIVE', activated_at = CURRENT_TIMESTAMP,
                        activation_reason = COALESCE(:reason, activation_reason),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """
                ),
                {"id": signal_id, "reason": None},
            )
        elif normalized == "INACTIVE":
            self.db.execute(
                text(
                    """
                    UPDATE market_signal_definitions
                    SET status = 'INACTIVE', deactivated_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """
                ),
                {"id": signal_id},
            )
        else:
            self.db.execute(
                text("UPDATE market_signal_definitions SET status = :status, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"id": signal_id, "status": normalized},
            )
        self.db.commit()
        return self.get_signal(signal_id)

    def evaluate(self, payload: Any) -> dict[str, Any]:
        signal_ids = getattr(payload, "signal_ids", None)
        active_only = bool(getattr(payload, "active_only", True))
        observation_date = getattr(payload, "observation_date", None) or self._latest_observation_date()
        save = bool(getattr(payload, "save", True))
        rows = self._target_signals(signal_ids=signal_ids, active_only=active_only)
        items = [self._evaluate_signal(dict(row), observation_date=observation_date, save=save) for row in rows]
        return {"items": items}

    def list_evaluations(self, signal_id: int, *, limit: int = 50) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                SELECT e.*, d.signal_code, d.signal_name
                FROM market_signal_evaluations e
                JOIN market_signal_definitions d ON d.id = e.signal_definition_id
                WHERE e.signal_definition_id = :id
                ORDER BY e.observation_date DESC, e.id DESC
                LIMIT :limit
                """
            ),
            {"id": signal_id, "limit": limit},
        ).mappings().all()
        return {"items": [self._evaluation_item(row) for row in rows]}

    def list_events(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                SELECT ev.*, d.signal_code, d.signal_name
                FROM market_signal_events ev
                JOIN market_signal_definitions d ON d.id = ev.signal_definition_id
                ORDER BY ev.event_date DESC, ev.id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
        return {"items": [dict(row) for row in rows]}

    def list_events_today(self) -> dict[str, Any]:
        today = self._latest_observation_date()
        rows = self.db.execute(
            text(
                """
                SELECT ev.*, d.signal_code, d.signal_name
                FROM market_signal_events ev
                JOIN market_signal_definitions d ON d.id = ev.signal_definition_id
                WHERE ev.event_date = :today
                ORDER BY ev.id DESC
                """
            ),
            {"today": today},
        ).mappings().all()
        return {"items": [dict(row) for row in rows], "observation_date": today}

    def signal_catalog(
        self,
        *,
        category: str | None = None,
        country: str | None = None,
        readiness: str | None = None,
        signal_readiness: str | None = None,
        profile_code: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_default_trend_models()
        items = self._signal_catalog_items()
        if category:
            items = [item for item in items if item.get("category_group") == category or item.get("category") == category]
        if country:
            items = [item for item in items if item.get("country") == country]
        if readiness:
            items = [item for item in items if item.get("readiness") == readiness]
        if signal_readiness:
            items = [item for item in items if item.get("signal_readiness") == signal_readiness]
        if profile_code:
            items = [item for item in items if item.get("recommended_profile_code") == profile_code]
        if search:
            needle = search.upper()
            items = [item for item in items if needle in str(item.get("item_code") or "").upper() or needle in str(item.get("item_name") or "").upper()]
        summary: dict[str, int] = {}
        for item in items:
            key = str(item.get("signal_readiness") or "UNKNOWN")
            summary[key] = summary.get(key, 0) + 1
        return {"items": items, "summary": summary, "total_count": len(items)}

    def list_model_profiles(self) -> dict[str, Any]:
        rows = self.db.execute(text("SELECT * FROM market_signal_model_profiles ORDER BY profile_code")).mappings().all()
        return {"items": [self._profile_item(dict(row)) for row in rows]}

    def preview_single_indicator_draft(self, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "payload", None) or {}
        item_type = str(data.get("item_type") or "INDICATOR").upper()
        item_code = str(data.get("item_code") or "").upper()
        if not item_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="item_code is required")
        catalog = self._catalog_lookup(item_type, item_code)
        if not catalog:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog item not found")
        profile_code = str(data.get("profile_code") or catalog["recommended_profile_code"])
        profile = self._profile_by_code(profile_code)
        model = self._model_from_profile(profile, item_type=item_type, item_code=item_code)
        model.update(self._validated_preview_configuration(data.get("configuration") or {}, catalog))
        period = str(data.get("period") or self._default_preview_period(str(catalog.get("frequency") or "DAILY"))).upper()
        observation_date = self._latest_observation_date()
        period_series, period_meta = self._series_for_preview_period(item_type, item_code, observation_date, period=period)
        diagnostic = self._trend_diagnostic(item_type, item_code, observation_date, model=model, source_series=period_series)
        period_meta.update(
            {
                "display_range_start": diagnostic.get("display_range_start") or period_meta.get("range_start"),
                "display_range_end": diagnostic.get("display_range_end") or period_meta.get("range_end"),
                "display_observation_count": diagnostic.get("display_observation_count", period_meta.get("observation_count", 0)),
                "trend_analysis_start": diagnostic.get("trend_analysis_start"),
                "trend_analysis_end": diagnostic.get("trend_analysis_end"),
                "trend_analysis_observation_count": diagnostic.get("trend_analysis_observation_count", 0),
                "trend_analysis_uses_full_display": diagnostic.get("trend_analysis_uses_full_display", False),
            }
        )
        if period_meta.get("trend_analysis_start") and period_meta.get("trend_analysis_end"):
            period_meta["trend_analysis_period_description"] = (
                f"{period_meta['trend_analysis_start']} ~ {period_meta['trend_analysis_end']} · "
                f"최근 {period_meta['trend_analysis_observation_count']}개 관측값"
            )
        else:
            period_meta["trend_analysis_period_description"] = "회귀·채널 분석 데이터 부족"
        existing = self._existing_single_signal(item_type, item_code, profile_code)
        explanation = self._trend_plain_explanation(catalog, diagnostic)
        chart_rows = diagnostic.get("series") or []
        return {
            "item": {
                "catalog": catalog,
                "profile": profile,
                "proposed_configuration": model,
                "applied_configuration": {key: model.get(key) for key in ("short_window", "medium_window", "trend_window", "channel_multiplier", "minimum_break_persistence", "false_break_window", "reversal_persistence")},
                "period": period_meta,
                "current_trend": diagnostic,
                "chart": chart_rows,
                "price_points": [{"date": row.get("date"), "value": row.get("value")} for row in chart_rows],
                "regression_points": [{"date": row.get("date"), "value": row.get("center")} for row in chart_rows if row.get("center") is not None],
                "upper_channel_points": [{"date": row.get("date"), "value": row.get("upper")} for row in chart_rows if row.get("upper") is not None],
                "lower_channel_points": [{"date": row.get("date"), "value": row.get("lower")} for row in chart_rows if row.get("lower") is not None],
                "plain_explanation": explanation,
                "recent_events": self._state_markers(diagnostic),
                "simulation_readiness": "READY" if catalog["signal_readiness"] != "DATA_INSUFFICIENT" else "DATA_INSUFFICIENT",
                "existing_signal": existing,
                "can_create_draft": catalog["signal_readiness"] not in {"DATA_INSUFFICIENT", "EXCLUDED"} and existing is None,
            }
        }

    def create_single_indicator_draft(self, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "payload", None) or {}
        return {"item": self._create_single_indicator_draft_from_data(data)}

    def create_single_indicator_drafts(self, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "payload", None) or {}
        rows = data.get("items") or []
        created = []
        skipped = []
        for row in rows:
            try:
                item = self._create_single_indicator_draft_from_data(dict(row))
                if item.get("created"):
                    created.append(item)
                else:
                    skipped.append(item)
            except HTTPException as exc:
                skipped.append({"input": row, "reason": exc.detail})
        return {"items": created, "created_count": len(created), "skipped_count": len(skipped), "skipped": skipped}

    def single_indicator_coverage_summary(self) -> dict[str, Any]:
        catalog = self._signal_catalog_items()
        summary: dict[str, int] = {}
        by_profile: dict[str, int] = {}
        for item in catalog:
            summary[item["signal_readiness"]] = summary.get(item["signal_readiness"], 0) + 1
            by_profile[item["recommended_profile_code"]] = by_profile.get(item["recommended_profile_code"], 0) + 1
        return {"item": {"total_count": len(catalog), "summary": summary, "by_profile": by_profile}}

    def validate_composite_template_readiness(self, template_id: int) -> dict[str, Any]:
        template = self.db.execute(text("SELECT * FROM market_signal_rule_templates WHERE id = :id"), {"id": template_id}).mappings().first()
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rule template not found")
        row = self._template_item(dict(template))
        catalog = {(item["item_type"], item["item_code"]): item for item in self._signal_catalog_items()}
        missing = []
        insufficient = []
        ready = []
        for code in row.get("required_indicator_codes") or []:
            found = next((item for key, item in catalog.items() if key[1] == code), None)
            if not found:
                missing.append(code)
            elif found["signal_readiness"] == "DATA_INSUFFICIENT":
                insufficient.append(code)
            else:
                ready.append(code)
        return {
            "item": {
                "template": row,
                "ready_codes": ready,
                "missing_codes": missing,
                "data_insufficient_codes": insufficient,
                "readiness_status": "READY" if not missing and not insufficient else "DATA_COMPLETION_REQUIRED",
                "can_copy_to_draft": not missing and not insufficient,
            }
        }

    def mark_validation_complete(self, signal_id: int, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "payload", None) or {}
        years = int(data.get("validation_period_years") or data.get("years") or 3)
        summary = data.get("validation_summary") or self.simulate(signal_id, years=years)
        self.db.execute(
            text(
                """
                UPDATE market_signal_definitions
                SET validation_status = 'VALIDATED',
                    validation_period_years = :years,
                    validation_completed_at = CURRENT_TIMESTAMP,
                    validation_summary_json = :summary,
                    activation_ready = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {"id": signal_id, "years": years, "summary": json.dumps(summary, ensure_ascii=False, sort_keys=True)},
        )
        self.db.commit()
        return {"item": self.get_signal(signal_id)}

    def activate_with_approval(self, signal_id: int, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "payload", None) or {}
        row = self._definition_row(signal_id)
        if str(row.get("validation_status") or "UNVALIDATED").upper() not in {"VALIDATED", "ACTIVATION_READY"} and not int(row.get("activation_ready") or 0):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="validation must be completed before activation")
        reason = str(data.get("reason") or data.get("activation_reason") or "").strip()
        self.db.execute(
            text(
                """
                UPDATE market_signal_definitions
                SET status = 'ACTIVE',
                    activated_at = CURRENT_TIMESTAMP,
                    activation_reason = :reason,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {"id": signal_id, "reason": reason or None},
        )
        self.db.commit()
        evaluation = self._evaluate_signal(dict(self._definition_row(signal_id)), observation_date=self._latest_observation_date(), save=True)
        return {"item": {"signal": self.get_signal(signal_id), "evaluation": evaluation}}

    def deactivate_with_reason(self, signal_id: int, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "payload", None) or {}
        reason = str(data.get("reason") or data.get("deactivation_reason") or "").strip()
        self.db.execute(
            text(
                """
                UPDATE market_signal_definitions
                SET status = 'INACTIVE',
                    deactivated_at = CURRENT_TIMESTAMP,
                    deactivation_reason = :reason,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {"id": signal_id, "reason": reason or None},
        )
        self.db.commit()
        return {"item": self.get_signal(signal_id)}

    def clone_signal_version(self, signal_id: int, payload: Any) -> dict[str, Any]:
        original = self.get_signal(signal_id)
        data = getattr(payload, "payload", None) or {}
        next_version = int(original.get("current_version") or 1) + 1
        clone = dict(original)
        clone.pop("id", None)
        clone["signal_code"] = f"{original['signal_code']}_V{next_version}"
        clone["signal_name"] = f"{original['signal_name']} v{next_version} 초안"
        clone["status"] = "DRAFT"
        clone["current_version"] = next_version
        clone["change_reason"] = data.get("reason") or "Cloned as new draft version"
        created = self.upsert_signal(clone)
        return {"item": {"source_signal_id": signal_id, "signal": created}}

    def overview(self) -> dict[str, Any]:
        observation_date = self._latest_observation_date()
        self._ensure_default_trend_models()
        singles = [self._overview_single_card(dict(row), observation_date) for row in self._trend_model_rows()]
        composite_rows = [dict(row) for row in self._target_signals(signal_ids=None, active_only=False)]
        composites = [self._overview_composite_card(row, observation_date) for row in composite_rows]
        phenomena = [self._overview_phenomenon_card(row, observation_date) for row in composite_rows]
        today = self.list_events_today()
        summary = {
            "trend_break_candidate": sum(1 for item in singles if item["evaluation_status"] == "BREAK_CANDIDATE"),
            "trend_break_confirmed": sum(1 for item in singles if item["evaluation_status"] == "BREAK_CONFIRMED"),
            "reversal_confirmed": sum(1 for item in singles if item["evaluation_status"] == "REVERSAL_CONFIRMED"),
            "false_break": sum(1 for item in singles if item["evaluation_status"] == "FALSE_BREAK"),
            "composite_candidate": sum(1 for item in composites if item["evaluation_status"] in {"WATCH", "ACTIVE", "STRENGTHENING"}),
            "phenomenon_confirmed": sum(1 for item in phenomena if item["evaluation_status"] in {"CONFIRMED", "STRENGTHENING"}),
            "data_insufficient": sum(1 for item in singles if item["evaluation_status"] == "DATA_INSUFFICIENT"),
        }
        return {
            "observation_date": observation_date,
            "summary": summary,
            "today_events": today["items"],
            "single_indicator_signals": singles,
            "composite_indicator_signals": composites,
            "objective_phenomena": phenomena,
            "templates": [],
        }

    def list_single_indicator_signals(self) -> dict[str, Any]:
        self._ensure_default_trend_models()
        rows = self._trend_model_rows()
        observation_date = self._latest_observation_date()
        return {
            "items": [
                self._single_indicator_item(dict(row), observation_date=observation_date, include_chart=False)
                for row in rows
            ]
        }

    def get_single_indicator_signal(self, model_id: int) -> dict[str, Any]:
        row = self._trend_model_row(model_id)
        return {"item": self._single_indicator_item(row, observation_date=self._latest_observation_date(), include_chart=True)}

    def evaluate_single_indicator(self, model_id: int, *, observation_date: str | None = None, save: bool = True) -> dict[str, Any]:
        row = self._trend_model_row(model_id)
        obs_date = observation_date or self._latest_observation_date()
        diagnostic = self._trend_diagnostic(row["item_type"], row["item_code"], obs_date, model=row)
        item = self._single_indicator_item(row, observation_date=obs_date, include_chart=False)
        item["evaluation_status"] = diagnostic["trend_health"]
        item["trend"] = diagnostic
        if save and row.get("signal_definition_id"):
            self._save_trend_episode_marker(int(row["signal_definition_id"]), row["item_code"], obs_date, diagnostic)
        return {"item": item}

    def simulate_single_indicator(self, model_id: int, *, years: int = 1) -> dict[str, Any]:
        row = self._trend_model_row(model_id)
        dates = self._item_dates(row["item_type"], row["item_code"], years=years)
        samples = [self._trend_diagnostic(row["item_type"], row["item_code"], obs_date, model=row) for obs_date in dates]
        state_counts: dict[str, int] = {}
        for sample in samples:
            state_counts[sample["trend_health"]] = state_counts.get(sample["trend_health"], 0) + 1
        return {
            "signal_id": model_id,
            "sample_count": len(samples),
            "triggered_count": sum(state_counts.get(key, 0) for key in ("BREAK_CONFIRMED", "REVERSAL_CONFIRMED")),
            "occurrence_count": sum(1 for sample in samples if sample["trend_health"] not in {"DATA_INSUFFICIENT", "TREND_INTACT"}),
            "state_counts": state_counts,
            "recent_samples": samples[-40:],
        }

    def trend_chart(self, model_id: int, *, observation_date: str | None = None) -> dict[str, Any]:
        row = self._trend_model_row(model_id)
        obs_date = observation_date or self._latest_observation_date()
        diagnostic = self._trend_diagnostic(row["item_type"], row["item_code"], obs_date, model=row)
        return {
            "item": self._single_indicator_item(row, observation_date=obs_date, include_chart=False),
            "series": diagnostic.pop("series"),
            "diagnostic": diagnostic,
        }

    def list_composite_signals(self) -> dict[str, Any]:
        rows = self._target_signals(signal_ids=None, active_only=False)
        return {"items": [self._composite_item(dict(row), include_conditions=False) for row in rows]}

    def get_composite_signal(self, signal_id: int) -> dict[str, Any]:
        return {"item": self._composite_item(dict(self._definition_row(signal_id)), include_conditions=True)}

    def evaluate_composite(self, signal_id: int, *, observation_date: str | None = None, save: bool = True) -> dict[str, Any]:
        signal = dict(self._definition_row(signal_id))
        obs_date = observation_date or self._latest_observation_date()
        evaluation = self._evaluate_signal(signal, observation_date=obs_date, save=save)
        item = self._composite_item(signal, include_conditions=True)
        item["evaluation"] = evaluation
        item["relation_diagnostic"] = self._composite_relation_diagnostic(signal, evaluation)
        return {"item": item}

    def simulate_composite(self, signal_id: int, *, years: int = 1) -> dict[str, Any]:
        result = self.simulate(signal_id, years=years)
        result["relation_type"] = dict(self._definition_row(signal_id)).get("relation_type") or "CONDITIONAL_RELATION"
        return result

    def list_phenomena(self) -> dict[str, Any]:
        rows = self._target_signals(signal_ids=None, active_only=False)
        observation_date = self._latest_observation_date()
        return {"items": [self._phenomenon_item(dict(row), observation_date=observation_date, evaluate_now=False) for row in rows]}

    def get_phenomenon(self, phenomenon_id: int) -> dict[str, Any]:
        row = dict(self._definition_row(phenomenon_id))
        return {"item": self._phenomenon_item(row, observation_date=self._latest_observation_date(), evaluate_now=True)}

    def evaluate_phenomenon(self, phenomenon_id: int, *, observation_date: str | None = None, save: bool = True) -> dict[str, Any]:
        row = dict(self._definition_row(phenomenon_id))
        obs_date = observation_date or self._latest_observation_date()
        item = self._phenomenon_item(row, observation_date=obs_date, evaluate_now=True)
        if save:
            self._upsert_episode(row, item)
        return {"item": item}

    def list_phenomenon_episodes(self, phenomenon_id: int) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                SELECT *
                FROM market_signal_episodes
                WHERE phenomenon_definition_id = :id
                ORDER BY COALESCE(trigger_date, created_at) DESC, id DESC
                LIMIT 100
                """
            ),
            {"id": phenomenon_id},
        ).mappings().all()
        return {"items": [self._episode_item(dict(row)) for row in rows]}

    def gpt_phenomenon_diagnosis(self, phenomenon_id: int, payload: Any) -> dict[str, Any]:
        phenomenon = self.evaluate_phenomenon(phenomenon_id, observation_date=getattr(payload, "observation_date", None), save=False)["item"]
        goal_text = ""
        if getattr(payload, "payload", None):
            goal_text = str(getattr(payload, "payload").get("goal_text") or "")
        prompt = (
            "DrCT objective phenomenon second-opinion assistant.\n"
            "Do not change DrCT state, score, rule status, or activation. Do not provide probabilities or buy/sell advice.\n"
            "Return economic meaning, alternative diagnosis, opposing diagnosis, additional checks, invalidation conditions, "
            "possible economic-flow handoff candidates, rule improvement proposals, unsupported engine features, and limitations.\n\n"
            f"User focus: {goal_text or '-'}\n\nPhenomenon snapshot:\n{json.dumps(phenomenon, ensure_ascii=False, indent=2)}"
        )
        return {
            "item": {
                "mode": "PROMPT_ONLY",
                "validation_status": "PROMPT_READY",
                "prompt": prompt,
                "drct_state_locked": True,
                "allowed_outputs": [
                    "economic_meaning",
                    "alternative_diagnosis",
                    "opposing_diagnosis",
                    "additional_checks",
                    "invalidation_conditions",
                    "economic_flow_candidates",
                    "rule_improvement_proposals",
                    "limitations",
                ],
            }
        }

    def list_evidence_sources(self) -> dict[str, Any]:
        self._ensure_evidence_sources()
        rows = self.db.execute(text("SELECT * FROM market_signal_evidence_sources ORDER BY source_type, source_code")).mappings().all()
        return {"items": [dict(row) for row in rows]}

    def upsert_evidence_source(self, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "payload", None) or {}
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        code = str(data.get("source_code") or data.get("item_code") or "").upper()
        if not code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_code is required")
        self.db.execute(
            text(
                """
                INSERT INTO market_signal_evidence_sources
                (source_code, source_name, source_type, item_type, item_code, provider, evidence_group_code, reliability_score, is_active)
                VALUES (:source_code, :source_name, :source_type, :item_type, :item_code, :provider, :evidence_group_code, :reliability_score, :is_active)
                ON CONFLICT(source_code) DO UPDATE SET
                    source_name = excluded.source_name,
                    source_type = excluded.source_type,
                    item_type = excluded.item_type,
                    item_code = excluded.item_code,
                    provider = excluded.provider,
                    evidence_group_code = excluded.evidence_group_code,
                    reliability_score = excluded.reliability_score,
                    is_active = excluded.is_active,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "source_code": code,
                "source_name": data.get("source_name") or code,
                "source_type": str(data.get("source_type") or "INDICATOR").upper(),
                "item_type": data.get("item_type"),
                "item_code": data.get("item_code"),
                "provider": data.get("provider"),
                "evidence_group_code": data.get("evidence_group_code"),
                "reliability_score": float(data.get("reliability_score") or 1.0),
                "is_active": 1 if data.get("is_active", True) else 0,
            },
        )
        self.db.commit()
        return self.list_evidence_sources()

    def list_rule_experiments(self) -> dict[str, Any]:
        rows = self.db.execute(text("SELECT * FROM market_signal_rule_experiments ORDER BY updated_at DESC, id DESC")).mappings().all()
        return {"items": [self._json_columns(dict(row), ("proposed_rule_json", "validation_summary_json")) for row in rows]}

    def list_rule_templates(self) -> dict[str, Any]:
        self._ensure_template_rows_visible()
        rows = self.db.execute(
            text(
                """
                SELECT *
                FROM market_signal_rule_templates
                ORDER BY
                    CASE status WHEN 'APPROVED' THEN 0 WHEN 'REVIEWED' THEN 1 WHEN 'DRAFT' THEN 2 ELSE 3 END,
                    category, template_name
                """
            )
        ).mappings().all()
        catalog = {item["code"]: item for item in self._indicator_catalog()}
        return {"items": [self._template_item(dict(row), catalog=catalog) for row in rows]}

    def copy_template_to_draft(self, template_id: int) -> dict[str, Any]:
        template = self.db.execute(text("SELECT * FROM market_signal_rule_templates WHERE id = :id"), {"id": template_id}).mappings().first()
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rule template not found")
        row = dict(template)
        config = json.loads(row.get("configuration_json") or "{}")
        codes = json.loads(row.get("required_indicator_codes_json") or "[]")
        signal_code = f"{row['template_code']}_DRAFT_{date.today().strftime('%Y%m%d')}"
        existing = self.db.execute(text("SELECT id FROM market_signal_definitions WHERE signal_code = :code"), {"code": signal_code}).scalar()
        if existing:
            return self.get_signal(int(existing))
        payload = {
            "signal_code": signal_code,
            "signal_name": f"{row['template_name']} 복제본",
            "description": row.get("description"),
            "category": row.get("category"),
            "signal_type": "COMPOSITE" if row.get("signal_level") != "SINGLE_INDICATOR" else "ATOMIC",
            "horizon": row.get("recommended_horizon") or "MEDIUM",
            "status": "DRAFT",
            "interpretation_direction": "MIXED",
            "phenomenon_template": row.get("template_name"),
            "process_template": row.get("evidence_summary"),
            "result_template": "검증 후 DRAFT 상태에서만 저장됩니다.",
            "persistence_periods": int(config.get("persistence_periods") or 2),
            "cooldown_periods": 1,
            "minimum_data_quality": 50,
            "conditions": self._template_conditions(codes, config),
            "change_reason": f"Copied from template {row['template_code']}",
        }
        copied = self.upsert_signal(payload)
        self.db.execute(
            text("UPDATE market_signal_rule_templates SET copied_count = copied_count + 1, usage_count = usage_count + 1, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {"id": template_id},
        )
        self.db.commit()
        return copied

    def gpt_rule_design(self, payload: Any) -> dict[str, Any]:
        goal_text = str(getattr(payload, "goal_text", "") or "").strip()
        result_json = getattr(payload, "gpt_result_json", None)
        catalog = self._signal_catalog_items()
        templates = self.list_rule_templates()["items"]
        catalog_text = "\n".join(
            f"- {item['item_type']} {item['item_code']}: {item['item_name']} / {item['country']} / {item['category_group']} / "
            f"{item['provider'] or '-'} / {item['frequency']} / readiness {item['readiness']} / signal {item['signal_readiness']} / "
            f"profile {item['recommended_profile_code']} / rows {item['data_count']} / {item['first_observation_date'] or '-'}..{item['latest_observation_date'] or '-'} / "
            f"transforms {','.join(item['supported_transforms']) or '-'}"
            for item in catalog[:120]
        )
        prompt = (
            "DrCT market signal rule design assistant.\n"
            "Use only the listed item_type/item_code pairs and transform enums. Do not present buy/sell advice or probabilities.\n"
            "DrCT may save only DRAFT after validation. Never activate automatically.\n\n"
            f"User goal:\n{goal_text}\n\nAll signal catalog:\n{catalog_text}\n"
            + "\n\nRule design UX constraints:\n"
            + "- Explain output in plain Korean sentences.\n"
            + "- Separate trigger_conditions, confirm_conditions, context_conditions, opposing_conditions, invalidation_conditions.\n"
            + "- Include confirmation_window, persistence, sensitive_variant, balanced_variant, conservative_variant.\n"
            + "- If an engine feature is unsupported, mark ENGINE_EXTENSION_REQUIRED.\n"
            + "- DrCT may save only DRAFT after validation. Never activate automatically.\n\n"
            + "Available templates:\n"
            + "\n".join(f"- {item['template_code']}: {item['template_name']} / {item['signal_level']} / {item['readiness_label']}" for item in templates[:40])
        )
        validation = []
        candidate = None
        if result_json:
            candidate = dict(result_json)
            validation = self._validate_gpt_signal_catalog_candidate(candidate, catalog)
            for bucket in ("trigger_conditions", "confirm_conditions", "context_conditions", "opposing_conditions", "invalidation_conditions"):
                for idx, condition in enumerate(candidate.get(bucket) or [], start=1):
                    role = str(condition.get("role") or bucket.replace("_conditions", "")).upper()
                    if role not in {"TRIGGER", "CONFIRM", "CONTEXT", "OPPOSING", "INVALIDATION", "REQUIRED"}:
                        validation.append(f"{bucket}[{idx}] invalid role: {role}")
        return {
            "item": {
                "mode": "PASTE_VALIDATE" if result_json else "PROMPT_ONLY",
                "prompt": prompt,
                "validation_status": "DRAFT_READY" if result_json and not validation else "PROMPT_READY" if not result_json else "NEEDS_REVISION",
                "validation_messages": validation,
                "candidate": candidate,
                "drct_save_policy": "DRAFT_ONLY",
            }
        }

    def _validate_gpt_signal_catalog_candidate(self, candidate: dict[str, Any], catalog: list[dict[str, Any]]) -> list[str]:
        messages: list[str] = []
        codes = {(item["item_type"], item["item_code"]): item for item in catalog}
        for bucket in ("trigger_conditions", "confirm_conditions", "context_conditions", "opposing_conditions", "invalidation_conditions"):
            for idx, condition in enumerate(candidate.get(bucket) or [], start=1):
                item_type = str(condition.get("item_type") or "INDICATOR").upper()
                item_code = str(condition.get("item_code") or "").upper()
                transform = str(condition.get("transform_type") or condition.get("transform") or "").upper()
                item = codes.get((item_type, item_code))
                if not item:
                    messages.append(f"{bucket}[{idx}] unknown item: {item_type} {item_code}")
                    continue
                if item["signal_readiness"] == "DATA_INSUFFICIENT":
                    messages.append(f"{bucket}[{idx}] data insufficient: {item_type} {item_code}")
                if transform and transform not in SUPPORTED_TRANSFORMS:
                    messages.append(f"{bucket}[{idx}] unsupported transform_type: {transform}")
                if transform and transform not in set(item.get("supported_transforms") or []) and transform in SUPPORTED_TRANSFORMS:
                    messages.append(f"{bucket}[{idx}] transform may need more data/profile support: {item_code} {transform}")
        return messages

    def create_rule_experiment(self, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "payload", None) or {}
        code = str(data.get("experiment_code") or f"EXP_{date.today().strftime('%Y%m%d')}_{abs(hash(json.dumps(data, sort_keys=True, default=str))) % 100000}").upper()
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_signal_rule_experiments
                (signal_definition_id, experiment_code, experiment_name, experiment_type, status, hypothesis, proposed_rule_json, validation_summary_json)
                VALUES (:signal_definition_id, :experiment_code, :experiment_name, :experiment_type, 'DRAFT', :hypothesis, :proposed_rule_json, :validation_summary_json)
                """
            ),
            {
                "signal_definition_id": data.get("signal_definition_id"),
                "experiment_code": code,
                "experiment_name": data.get("experiment_name") or code,
                "experiment_type": str(data.get("experiment_type") or "CHALLENGER").upper(),
                "hypothesis": data.get("hypothesis"),
                "proposed_rule_json": json.dumps(data.get("proposed_rule") or {}, ensure_ascii=False, sort_keys=True),
                "validation_summary_json": json.dumps(data.get("validation_summary") or {}, ensure_ascii=False, sort_keys=True),
            },
        )
        self.db.commit()
        return self.list_rule_experiments()

    def set_rule_experiment_status(self, experiment_id: int, status_value: str) -> dict[str, Any]:
        self.db.execute(
            text("UPDATE market_signal_rule_experiments SET status = :status, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {"id": experiment_id, "status": status_value.upper()},
        )
        self.db.commit()
        return self.list_rule_experiments()

    def create_user_review(self, payload: Any) -> dict[str, Any]:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        self.db.execute(
            text(
                """
                INSERT INTO market_signal_user_reviews
                (signal_definition_id, episode_id, review_target_type, review_target_id, reviewer, review_status,
                 usefulness_score, accuracy_score, review_note)
                VALUES (:signal_definition_id, :episode_id, :review_target_type, :review_target_id, :reviewer, :review_status,
                        :usefulness_score, :accuracy_score, :review_note)
                """
            ),
            data,
        )
        self.db.commit()
        rows = self.db.execute(text("SELECT * FROM market_signal_user_reviews ORDER BY id DESC LIMIT 50")).mappings().all()
        return {"items": [dict(row) for row in rows]}

    def indicator_catalog(self) -> dict[str, Any]:
        return {"items": self._indicator_catalog()}

    def condition_preview(self, payload: Any) -> dict[str, Any]:
        raw_condition = getattr(payload, "condition", None) or {}
        condition = raw_condition.model_dump() if hasattr(raw_condition, "model_dump") else dict(raw_condition)
        observation_date = getattr(payload, "observation_date", None) or self._latest_observation_date()
        window = int(condition.get("window_size") or 20)
        series = self._series(str(condition.get("item_type") or "INDICATOR"), str(condition.get("item_code") or ""), observation_date, limit=max(window + 260, 280))
        preview = self._evaluate_condition(condition, observation_date)
        return {
            "observation_date": observation_date,
            "preview": preview,
            "series": series[-max(window * 2, 30):],
        }

    def simulate(self, signal_id: int, *, years: int = 1) -> dict[str, Any]:
        signal = dict(self._definition_row(signal_id))
        conditions = [dict(row) for row in self._condition_rows(signal_id)]
        dates = self._simulation_dates(signal_id, years=years)
        samples = [self._evaluate_signal(signal, observation_date=obs_date, save=False, conditions_override=conditions) for obs_date in dates]
        scores = [float(item["score"]) for item in samples if item["state"] != "DATA_INSUFFICIENT"]
        active = [item for item in samples if item["state"] in {"ACTIVE", "STRENGTHENING", "WEAKENING"}]
        persistence_runs = self._persistence_runs(samples)
        condition_pass_counts: dict[str, int] = {}
        required_satisfaction_count = 0
        confirm_contribution_count = 0
        opposing_penalty_count = 0
        for sample in samples:
            if sample["required_total_count"] and sample["required_pass_count"] >= sample["required_total_count"]:
                required_satisfaction_count += 1
            if sample["confirm_pass_count"]:
                confirm_contribution_count += 1
            if sample["opposing_pass_count"]:
                opposing_penalty_count += 1
            for evidence in [*sample.get("evidence", []), *sample.get("opposing_evidence", [])]:
                key = str(evidence.get("condition_id") or evidence.get("item_code") or "-")
                condition_pass_counts[key] = condition_pass_counts.get(key, 0) + 1
        warnings: list[str] = []
        active_ratio = len(active) / len(samples) if samples else 0
        if samples and active_ratio > 0.45:
            warnings.append("TOO_FREQUENT")
        if samples and 0 < active_ratio < 0.03:
            warnings.append("TOO_RARE")
        if any(item["state"] == "DATA_INSUFFICIENT" for item in samples):
            warnings.append("DATA_INSUFFICIENT_PERIODS")
        duplicate_keys = self._duplicate_condition_keys(signal_id)
        if duplicate_keys:
            warnings.append("DUPLICATE_CONDITION:" + ",".join(duplicate_keys[:5]))
        return {
            "signal_id": signal_id,
            "sample_count": len(samples),
            "triggered_count": len(active),
            "occurrence_count": len(persistence_runs),
            "average_persistence": round(sum(persistence_runs) / len(persistence_runs), 2) if persistence_runs else None,
            "median_persistence": round(statistics.median(persistence_runs), 2) if persistence_runs else None,
            "max_persistence": max(persistence_runs) if persistence_runs else 0,
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
            "median_score": round(statistics.median(scores), 2) if scores else None,
            "active_ratio": round(len(active) / len(samples), 4) if samples else None,
            "data_insufficient_count": sum(1 for item in samples if item["state"] == "DATA_INSUFFICIENT"),
            "condition_pass_counts": condition_pass_counts,
            "required_satisfaction_count": required_satisfaction_count,
            "confirm_contribution_count": confirm_contribution_count,
            "opposing_penalty_count": opposing_penalty_count,
            "condition_contributions": self._condition_contributions(samples, conditions),
            "variant_summaries": self._variant_summaries(signal, conditions, dates),
            "transition_points": self._transition_points(samples),
            "warnings": warnings,
            "recent_samples": samples[-20:],
        }

    def gpt_rule_draft(self, payload: Any) -> dict[str, Any]:
        goal_text = str(getattr(payload, "goal_text", "") or "").strip()
        result_json = getattr(payload, "gpt_result_json", None)
        catalog = self._indicator_catalog()
        prompt = self._gpt_prompt(goal_text, catalog)
        validation_messages: list[str] = []
        candidate = None
        status_value = "PROMPT_READY"
        if result_json:
            candidate = dict(result_json)
            validation_messages = self._validate_gpt_candidate(candidate, catalog)
            status_value = "REGISTRABLE" if not validation_messages else "NEEDS_REVISION"
        return {
            "mode": "PASTE_VALIDATE" if result_json else "PROMPT_ONLY",
            "prompt": prompt,
            "validation_status": status_value,
            "validation_messages": validation_messages,
            "candidate": candidate,
        }

    def _ensure_default_trend_models(self) -> None:
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_signal_trend_models
                (signal_definition_id, item_type, item_code, short_window, medium_window, trend_window)
                SELECT DISTINCT c.signal_definition_id, c.item_type, c.item_code,
                       CASE COALESCE(i.data_frequency, 'DAILY') WHEN 'MONTHLY' THEN 6 WHEN 'WEEKLY' THEN 8 ELSE 20 END,
                       CASE COALESCE(i.data_frequency, 'DAILY') WHEN 'MONTHLY' THEN 12 WHEN 'WEEKLY' THEN 26 ELSE 60 END,
                       CASE COALESCE(i.data_frequency, 'DAILY') WHEN 'MONTHLY' THEN 36 WHEN 'WEEKLY' THEN 52 ELSE 120 END
                FROM market_signal_conditions c
                LEFT JOIN market_indicators i ON i.indicator_code = c.item_code
                WHERE c.item_code IS NOT NULL AND c.item_code <> ''
                """
            )
        )
        self.db.commit()

    def _overview_single_card(self, row: dict[str, Any], observation_date: str) -> dict[str, Any]:
        item = self._single_indicator_item(row, observation_date=observation_date, include_chart=True)
        diagnostic = dict(item.get("diagnostic") or {})
        sparkline = self._sparkline_points(item.get("series") or [])
        item.pop("series", None)
        item["card_type"] = "single"
        item["status_label"] = self._status_label(item["evaluation_status"])
        item["rule_status_label"] = self._rule_status_label(item["rule_status"])
        item["number_label"] = self._single_number_label(item)
        item["trend_label"] = self._trend_label(item["trend_state"])
        item["sparkline"] = sparkline
        item["sparkline_markers"] = self._state_markers(diagnostic)
        item["next_checks"] = self._single_next_checks(diagnostic)
        item["compact_metrics"] = {
            "trend_strength": self._score_100(diagnostic.get("trend_strength")),
            "channel_position": diagnostic.get("channel_position"),
            "r_squared": diagnostic.get("r_squared"),
        }
        item["technical_summary"] = f"{item['item_code']} / {item.get('frequency') or '-'} / {item.get('provider') or '-'}"
        return item

    def _overview_composite_card(self, signal: dict[str, Any], observation_date: str) -> dict[str, Any]:
        evaluation = self._evaluate_signal(signal, observation_date=observation_date, save=False)
        relation = self._composite_relation_diagnostic(signal, evaluation)
        conditions = [dict(row) for row in self._condition_rows(int(signal["id"]))]
        trigger_conditions = [row for row in conditions if str(row.get("condition_role")).upper() in {"REQUIRED", "TRIGGER"}]
        trigger_chart = []
        if trigger_conditions:
            first = trigger_conditions[0]
            series = self._series(first["item_type"], first["item_code"], observation_date, limit=60)
            trigger_chart = self._sparkline_points(series)
        return {
            "id": signal["id"],
            "card_type": "composite",
            "signal_code": signal.get("signal_code"),
            "signal_name": signal.get("signal_name"),
            "rule_status": signal.get("status"),
            "rule_status_label": self._rule_status_label(signal.get("status")),
            "evaluation_status": evaluation["state"],
            "status_label": self._status_label(evaluation["state"]),
            "observation_date": observation_date,
            "number_label": f"현상 충족률 {self._score_100(evaluation.get('score'))}점",
            "score": evaluation.get("score"),
            "sparkline": trigger_chart,
            "timeline": self._relation_timeline(evaluation),
            "trigger_summary": f"시작 조건 {evaluation['required_pass_count']}/{evaluation['required_total_count']}",
            "confirm_summary": f"지속 확인 {evaluation['confirm_pass_count']}/{max(1, relation['minimum_confirm_count'])}",
            "opposing_summary": f"반대 근거 {evaluation['opposing_pass_count']}개",
            "relation_diagnostic": relation,
            "next_checks": self._next_checks(signal, evaluation.get("missing_data") or []),
        }

    def _overview_phenomenon_card(self, signal: dict[str, Any], observation_date: str) -> dict[str, Any]:
        item = self._phenomenon_item(signal, observation_date=observation_date, evaluate_now=True)
        item["card_type"] = "phenomenon"
        item["status_label"] = self._status_label(item["evaluation_status"])
        item["rule_status_label"] = self._rule_status_label(item.get("rule_status"))
        item["number_label"] = f"현상 충족률 {self._score_100(item.get('fulfillment_score'))}점"
        item["start_condition_summary"] = f"시작 조건 {len(item['trigger_evidence'])}개 충족"
        item["confirm_condition_summary"] = f"지속 확인 {len(item['confirm_evidence'])}개 충족"
        item["uncertainty_summary"] = f"반대 {len(item['opposing_evidence'])} / 데이터 부족 {len(item['missing_conditions'])}"
        item["plain_judgement"] = self._plain_phenomenon_judgement(item)
        item["timeline"] = self._phenomenon_timeline(int(signal["id"]))
        return item

    def _sparkline_points(self, series: list[dict[str, Any]], *, max_points: int = 56) -> list[dict[str, Any]]:
        if not series:
            return []
        source = series[-max_points:]
        values = [float(row["value"]) for row in source if row.get("value") is not None]
        if not values:
            return []
        low = min(values)
        high = max(values)
        span = high - low or 1
        points = []
        for idx, row in enumerate(source):
            value = row.get("value")
            if value is None:
                continue
            points.append(
                {
                    "date": row.get("date"),
                    "value": value,
                    "x": round(idx / max(len(source) - 1, 1), 4),
                    "y": round(1 - ((float(value) - low) / span), 4),
                    "center": row.get("center"),
                    "upper": row.get("upper"),
                    "lower": row.get("lower"),
                }
            )
        return points

    @staticmethod
    def _state_markers(diagnostic: dict[str, Any]) -> list[str]:
        markers = []
        for key, label in (
            ("trend_break_up", "상단 이탈 후보"),
            ("trend_break_down", "하단 이탈 후보"),
            ("break_confirmed_up", "상단 이탈 확인"),
            ("break_confirmed_down", "하단 이탈 확인"),
            ("false_break_up", "상단 False Break"),
            ("false_break_down", "하단 False Break"),
            ("reversal_confirmed_up", "상승 반전 확인"),
            ("reversal_confirmed_down", "하락 반전 확인"),
        ):
            if diagnostic.get(key):
                markers.append(label)
        return markers

    @staticmethod
    def _status_label(status_value: Any) -> str:
        labels = {
            "TREND_INTACT": "추세 유지",
            "TREND_WEAKENING": "추세 약화",
            "BREAK_CANDIDATE": "추세 이탈 후보",
            "BREAK_CONFIRMED": "추세 이탈 확인",
            "REVERSAL_CONFIRMED": "반전 확인",
            "FALSE_BREAK": "일시 이탈 후 복귀",
            "TREND_RESUMED": "추세 재개",
            "SIDEWAYS": "횡보",
            "DATA_INSUFFICIENT": "데이터 부족",
            "WATCH": "시작 조건",
            "ACTIVE": "확인",
            "STRENGTHENING": "강화",
            "WEAKENING": "약화",
            "CONFIRMED": "확인",
            "CANDIDATE": "시작 조건",
            "NOT_EVALUATED": "미평가",
        }
        return labels.get(str(status_value or "").upper(), str(status_value or "-"))

    @staticmethod
    def _rule_status_label(status_value: Any) -> str:
        return {
            "DRAFT": "초안",
            "ACTIVE": "운영",
            "INACTIVE": "중지",
            "ARCHIVED": "중지",
        }.get(str(status_value or "").upper(), str(status_value or "-"))

    @staticmethod
    def _trend_label(trend_state: Any) -> str:
        return {
            "UP_TREND": "상승 추세",
            "DOWN_TREND": "하락 추세",
            "SIDEWAYS": "횡보",
            "UNSTABLE": "불안정",
            "INSUFFICIENT_DATA": "데이터 부족",
        }.get(str(trend_state or "").upper(), str(trend_state or "-"))

    def _single_number_label(self, item: dict[str, Any]) -> str:
        unit = item.get("unit_label") or ""
        code = str(item.get("item_code") or "")
        value = item.get("latest_value")
        if code.endswith("_SPREAD"):
            return f"금리차 {self._format_number(value)}{unit}"
        if "RELATIVE" in code:
            return f"상대강도 지수 {self._format_number(value)}"
        return f"현재값 {self._format_number(value)}{unit}"

    @staticmethod
    def _format_number(value: Any) -> str:
        if not isinstance(value, (int, float)):
            return "-"
        if abs(float(value)) >= 100:
            return f"{float(value):,.2f}"
        return f"{float(value):.2f}"

    @staticmethod
    def _score_100(value: Any) -> int:
        if not isinstance(value, (int, float)):
            return 0
        return max(0, min(100, int(round(float(value)))))

    @staticmethod
    def _single_next_checks(diagnostic: dict[str, Any]) -> list[str]:
        if diagnostic.get("trend_health") == "BREAK_CANDIDATE":
            return ["채널 이탈이 2회 이상 지속되는지 확인", "단기 slope가 같은 방향으로 유지되는지 확인"]
        if diagnostic.get("trend_health") == "FALSE_BREAK":
            return ["기존 채널 안에서 추세가 복귀하는지 확인", "반대 방향 이탈이 재발하는지 확인"]
        if diagnostic.get("trend_health") == "DATA_INSUFFICIENT":
            return ["데이터 수집 완료 후 재평가"]
        return ["현재 추세가 유지되는지 확인", "채널 상단·하단 접근 여부 확인"]

    def _trend_plain_explanation(self, catalog: dict[str, Any], diagnostic: dict[str, Any]) -> dict[str, Any]:
        name = catalog.get("item_name") or catalog.get("item_code") or "해당 지표"
        health = str(diagnostic.get("trend_health") or "NOT_EVALUATED")
        strength = float(diagnostic.get("trend_strength") or 0)
        r_squared = diagnostic.get("r_squared")
        channel_position = diagnostic.get("channel_position")
        judgement_map = {
            "TREND_INTACT": f"{name}의 현재 추세는 비교적 유지되고 있습니다.",
            "TREND_WEAKENING": f"{name}는 최근 관측 구간에서 뚜렷한 방향성이 약해졌습니다.",
            "BREAK_CANDIDATE": f"{name}가 추세 채널 이탈 후보 구간에 들어왔습니다.",
            "BREAK_CONFIRMED": f"{name}의 추세 이탈이 최근 관측에서 확인되었습니다.",
            "REVERSAL_CONFIRMED": f"{name}에서 기존 추세와 반대 방향 전환 신호가 확인되었습니다.",
            "FALSE_BREAK": f"{name}는 일시적으로 채널을 벗어난 뒤 기존 추세로 복귀하는 모습입니다.",
            "DATA_INSUFFICIENT": f"{name}는 추세 판단에 필요한 관측값이 부족합니다.",
        }
        reasons = []
        if strength <= 0:
            reasons.append("추세 강도 0점: 현재 기울기와 방향 일관성이 추세 인정 기준에 미달합니다.")
        elif strength < 1:
            reasons.append("추세 강도가 낮아 방향 판단의 신뢰도가 제한적입니다.")
        if isinstance(r_squared, (int, float)) and r_squared < 0.18:
            reasons.append("회귀 설명력 R²가 낮아 직선 추세로 설명하기 어렵습니다.")
        if isinstance(channel_position, (int, float)):
            if channel_position > 1:
                reasons.append("최근값이 상단 추세 채널 밖에 있습니다.")
            elif channel_position < 0:
                reasons.append("최근값이 하단 추세 채널 밖에 있습니다.")
            else:
                reasons.append("최근값은 추세 채널 내부에 있습니다.")
        if not reasons:
            reasons.append("최근값, 회귀 기울기, 추세 채널 위치를 기준으로 판정했습니다.")
        data_count = int(catalog.get("data_count") or 0)
        minimum = self._signal_minimum_rows(str(catalog.get("frequency") or "DAILY"), str(catalog.get("item_code") or ""))
        caution = "장기 검증 전에는 초안으로만 사용하세요."
        if data_count < minimum:
            caution = f"현재 {data_count}건 / 최소 {minimum}건으로 {minimum - data_count}건이 추가로 필요합니다."
        return {
            "judgement": judgement_map.get(health, f"{name}의 현재 추세를 임시 분석했습니다."),
            "reasons": reasons,
            "caution": caution,
            "next_step": "그래프와 추천 분석 기준을 확인한 뒤 시그널 초안 생성 여부를 결정하세요.",
        }

    @staticmethod
    def _relation_timeline(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for evidence in evaluation.get("evidence", []):
            role = str(evidence.get("role") or "").upper()
            if role in {"REQUIRED", "TRIGGER"}:
                label = "Trigger 발생"
            elif role == "CONFIRM":
                label = "Confirm 발생"
            elif role == "CONTEXT":
                label = "Context 확인"
            else:
                label = role or "근거"
            rows.append({"label": label, "item_code": evidence.get("item_code"), "passed": evidence.get("passed")})
        for evidence in evaluation.get("opposing_evidence", []):
            rows.append({"label": "Opposing 발생", "item_code": evidence.get("item_code"), "passed": evidence.get("passed")})
        return rows[:8]

    @staticmethod
    def _plain_phenomenon_judgement(item: dict[str, Any]) -> str:
        name = item.get("phenomenon_name") or item.get("phenomenon_code")
        status_value = item.get("evaluation_status")
        if status_value in {"CONFIRMED", "STRENGTHENING"}:
            return f"{name} 조건이 확인 구간에 들어왔습니다."
        if status_value in {"CANDIDATE", "PARTIALLY_CONFIRMED"}:
            return f"{name} 시작 조건은 보이지만 추가 확인이 필요합니다."
        if status_value == "DATA_INSUFFICIENT":
            return f"{name} 판단에는 데이터가 더 필요합니다."
        return f"{name} 현상은 아직 확인되지 않았습니다."

    def _ensure_template_rows_visible(self) -> None:
        # Schema seeding is handled at application startup. This small read keeps older app sessions harmless.
        self.db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='market_signal_rule_templates'")).first()

    def _template_item(self, row: dict[str, Any], *, catalog: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        row["configuration"] = json.loads(row.pop("configuration_json") or "{}")
        codes = json.loads(row.pop("required_indicator_codes_json") or "[]")
        row["required_indicator_codes"] = codes
        catalog_map = catalog if catalog is not None else {item["code"]: item for item in self._indicator_catalog()}
        ready = [code for code in codes if catalog_map.get(code, {}).get("classification") == "AVAILABLE"]
        row["readiness_label"] = "데이터 준비 완료" if len(ready) == len(codes) else f"데이터 준비 {len(ready)}/{len(codes)}"
        row["recent_3y_occurrence_count"] = 0
        row["evidence_grade"] = "기본"
        return row

    @staticmethod
    def _template_conditions(codes: list[str], config: dict[str, Any]) -> list[dict[str, Any]]:
        trigger = set((config.get("suggested_roles") or {}).get("trigger") or codes[:1])
        confirm = set((config.get("suggested_roles") or {}).get("confirm") or codes[1:])
        rows = []
        for idx, code in enumerate(codes, start=1):
            role = "TRIGGER" if code in trigger else "CONFIRM" if code in confirm else "CONTEXT"
            rows.append(
                {
                    "condition_group": "A",
                    "condition_role": role,
                    "item_type": "INDICATOR",
                    "item_code": code,
                    "transform_type": config.get("default_transform") or "TREND_STATE",
                    "window_size": 20,
                    "comparison_operator": "!=",
                    "threshold_type": "ABSOLUTE",
                    "threshold_value": 0,
                    "threshold_secondary": None,
                    "weight": 20 if role == "TRIGGER" else 10,
                    "is_required": role == "TRIGGER",
                    "sort_order": idx,
                }
            )
        return rows

    def _signal_catalog_items(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        index_rows = self.db.execute(
            text(
                """
                SELECT 'INDEX' AS item_type, i.index_code AS item_code, i.index_name AS item_name,
                       i.category, i.market AS country, i.provider, i.provider_symbol, 'DAILY' AS frequency,
                       i.currency AS unit_label, i.is_active,
                       COALESCE(v.data_count, 0) AS data_count,
                       v.first_observation_date, v.latest_observation_date
                FROM market_indexes i
                LEFT JOIN (
                    SELECT index_code, COUNT(*) AS data_count, MIN(price_date) AS first_observation_date, MAX(price_date) AS latest_observation_date
                    FROM market_index_daily_prices
                    WHERE close_price IS NOT NULL
                    GROUP BY index_code
                ) v ON v.index_code = i.index_code
                WHERE i.is_active = 1
                """
            )
        ).mappings().all()
        indicator_rows = self.db.execute(
            text(
                """
                SELECT 'INDICATOR' AS item_type, i.indicator_code AS item_code, i.indicator_name AS item_name,
                       i.category,
                       CASE
                         WHEN i.indicator_code LIKE 'US_%' OR i.category LIKE 'GLOBAL_%' THEN 'US'
                         ELSE 'KR'
                       END AS country,
                       COALESCE(m.provider, CASE WHEN i.category = 'DERIVED' THEN 'DERIVED' ELSE NULL END) AS provider,
                       m.provider_symbol,
                       i.data_frequency AS frequency,
                       i.unit_label,
                       i.is_active,
                       COALESCE(v.data_count, 0) AS data_count,
                       v.first_observation_date, v.latest_observation_date
                FROM market_indicators i
                LEFT JOIN market_indicator_provider_mappings m ON m.indicator_code = i.indicator_code AND m.is_enabled = 1
                LEFT JOIN (
                    SELECT indicator_code, COUNT(*) AS data_count, MIN(value_date) AS first_observation_date, MAX(value_date) AS latest_observation_date
                    FROM market_indicator_values
                    WHERE COALESCE(value, close_value) IS NOT NULL
                    GROUP BY indicator_code
                ) v ON v.indicator_code = i.indicator_code
                WHERE i.is_active = 1
                """
            )
        ).mappings().all()
        for row in [*index_rows, *indicator_rows]:
            item = dict(row)
            item["item_code"] = str(item["item_code"]).upper()
            item["source_kind"] = "DERIVED_INDICATOR" if item["item_type"] == "INDICATOR" and str(item.get("provider") or "").upper() == "DERIVED" else ("MARKET_INDEX" if item["item_type"] == "INDEX" else "MARKET_INDICATOR")
            item["category_group"] = self._category_group(item)
            item["recommended_profile_code"], item["recommended_profile_reason"] = self._recommended_profile(item)
            item["readiness"] = self._base_readiness(item)
            item["supported_transforms"] = self._profile_supported_transforms(item["recommended_profile_code"], int(item.get("data_count") or 0))
            item.update(self._signal_registration_state(item))
            if int(item.get("data_count") or 0) > 0:
                item["sparkline"] = self._sparkline_points(self._series(item["item_type"], item["item_code"], str(item.get("latest_observation_date") or self._latest_observation_date()), limit=48))
            else:
                item["sparkline"] = []
            rows.append(item)
        rows.sort(key=lambda item: (str(item.get("country") or ""), str(item.get("category_group") or ""), str(item.get("item_code") or "")))
        return rows

    def _catalog_lookup(self, item_type: str, item_code: str) -> dict[str, Any] | None:
        return next((item for item in self._signal_catalog_items() if item["item_type"] == item_type and item["item_code"] == item_code), None)

    def _signal_registration_state(self, item: dict[str, Any]) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                SELECT d.status, COUNT(*) AS count_value
                FROM market_signal_conditions c
                JOIN market_signal_definitions d ON d.id = c.signal_definition_id
                WHERE c.item_type = :item_type AND c.item_code = :item_code
                GROUP BY d.status
                """
            ),
            {"item_type": item["item_type"], "item_code": item["item_code"]},
        ).mappings().all()
        status_counts = {str(row["status"]): int(row["count_value"]) for row in rows}
        trend_count = self.db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM market_signal_trend_models
                WHERE item_type = :item_type AND item_code = :item_code AND is_active = 1
                """
            ),
            {"item_type": item["item_type"], "item_code": item["item_code"]},
        ).scalar() or 0
        active_count = status_counts.get("ACTIVE", 0)
        draft_count = status_counts.get("DRAFT", 0)
        if item["readiness"] == "DATA_INSUFFICIENT":
            signal_readiness = "DATA_INSUFFICIENT"
        elif active_count:
            signal_readiness = "SIGNAL_ACTIVE"
        elif draft_count:
            signal_readiness = "SIGNAL_DRAFT"
        elif trend_count:
            signal_readiness = "SIGNAL_NOT_REGISTERED"
        else:
            signal_readiness = "SIGNAL_NOT_REGISTERED"
        return {
            "registered_signal_count": sum(status_counts.values()),
            "active_signal_count": active_count,
            "draft_signal_count": draft_count,
            "trend_model_count": int(trend_count),
            "signal_readiness": signal_readiness,
            "exclusion_reason": None,
        }

    def _base_readiness(self, item: dict[str, Any]) -> str:
        minimum = self._signal_minimum_rows(str(item.get("frequency") or "DAILY"), str(item.get("item_code") or ""))
        return "SIGNAL_READY" if int(item.get("data_count") or 0) >= minimum else "DATA_INSUFFICIENT"

    @staticmethod
    def _category_group(item: dict[str, Any]) -> str:
        code = str(item.get("item_code") or "").upper()
        category = str(item.get("category") or "").upper()
        market = str(item.get("country") or "").upper()
        if item.get("item_type") == "INDEX" and code in {"KOSPI", "KOSDAQ", "KOSPI200", "KOSDAQ150", "KRX100"}:
            return "DOMESTIC_STOCK_MARKET"
        if item.get("item_type") == "INDEX":
            if code == "GOLD_KRX" or "금" in str(item.get("category") or ""):
                return "ENERGY_COMMODITY"
            if "업종" in str(item.get("category") or "") or market in {"KOSPI", "KOSDAQ"}:
                return "DOMESTIC_SECTOR"
            if market in {"KR", "KRX"}:
                return "DOMESTIC_STOCK_MARKET"
            return "US_MARKET"
        if category == "FX":
            return "FX"
        if category in {"RATE", "GLOBAL_RATE"}:
            return "DOMESTIC_RATE" if str(item.get("country") or "").upper() == "KR" else "US_MARKET"
        if category in {"INFLATION", "ECONOMY", "EMPLOYMENT_CONSUMPTION", "CREDIT_LIQUIDITY"}:
            return "INFLATION_ECONOMY"
        if category in {"ENERGY", "COMMODITY"}:
            return "ENERGY_COMMODITY"
        if category == "DERIVED":
            return "DERIVED"
        if category.startswith("GLOBAL_"):
            return "US_MARKET"
        return category or "OTHER"

    def _recommended_profile(self, item: dict[str, Any]) -> tuple[str, str]:
        code = str(item.get("item_code") or "").upper()
        category = str(item.get("category") or "").upper()
        frequency = str(item.get("frequency") or "").upper()
        if code == "GOLD_KRX":
            return "COMMODITY_TREND", "금 현물은 원자재/안전자산 추세형이 적합합니다."
        if item.get("item_type") == "INDEX":
            return "MARKET_PRICE_TREND", "시장 가격/업종 지수에는 가격 추세형이 적합합니다."
        if code in {"BASE_RATE", "US_FED_FUNDS"}:
            return "POLICY_RATE_REGIME", "정책금리는 일반 채널보다 변경 방향과 동결 기간이 중요합니다."
        if code.endswith("_VOLATILITY") or code == "US_VIX":
            return "VOLATILITY_REGIME", "변동성 지표는 체제 전환과 백분위 분석이 적합합니다."
        if "SPREAD" in code or "REAL_POLICY_RATE" in code:
            return "SPREAD_REGIME", "스프레드/실질금리는 방향과 기준선 위치가 중요합니다."
        if "RELATIVE" in code:
            return "RELATIVE_STRENGTH", "상대강도 지표는 시장 대비 우위/열위 전환을 봅니다."
        if category == "FX":
            return "FX_TREND", "환율 지표는 변동성 조정 추세 분석이 적합합니다."
        if category in {"RATE", "GLOBAL_RATE"}:
            return "YIELD_TREND", "시장금리는 기울기와 추세 반전 분석이 적합합니다."
        if category in {"INFLATION"} or frequency == "MONTHLY":
            return "MACRO_MOM_YOY_TREND", "월간 물가/경기 지표는 MoM/YoY 추세가 중요합니다."
        if category in {"ECONOMY", "EMPLOYMENT_CONSUMPTION", "CREDIT_LIQUIDITY"}:
            return "SENTIMENT_TREND", "심리·경기 지표는 6/12개월 추세 확인이 적합합니다."
        if category in {"ENERGY", "COMMODITY"}:
            return "COMMODITY_TREND", "원자재 가격은 추세 채널과 반전 분석이 적합합니다."
        return "MARKET_PRICE_TREND", "기본 가격 추세형을 추천합니다."

    def _profile_supported_transforms(self, profile_code: str, data_count: int) -> list[str]:
        profile = self._profile_by_code(profile_code)
        transforms = profile.get("supported_transforms") or []
        available = set(self._supported_transforms_for_rows(data_count))
        return [item for item in transforms if item in available or item in SUPPORTED_TRANSFORMS]

    def _profile_by_code(self, profile_code: str) -> dict[str, Any]:
        row = self.db.execute(text("SELECT * FROM market_signal_model_profiles WHERE profile_code = :code"), {"code": profile_code}).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"model profile not found: {profile_code}")
        return self._profile_item(dict(row))

    @staticmethod
    def _profile_item(row: dict[str, Any]) -> dict[str, Any]:
        row["applicable_categories"] = json.loads(row.pop("applicable_categories_json") or "[]")
        row["applicable_frequencies"] = json.loads(row.pop("applicable_frequencies_json") or "[]")
        row["default_configuration"] = json.loads(row.pop("default_configuration_json") or "{}")
        row["supported_transforms"] = json.loads(row.pop("supported_transforms_json") or "[]")
        return row

    @staticmethod
    def _model_from_profile(profile: dict[str, Any], *, item_type: str, item_code: str) -> dict[str, Any]:
        config = dict(profile.get("default_configuration") or {})
        return {
            "id": None,
            "signal_definition_id": None,
            "item_type": item_type,
            "item_code": item_code,
            "model_type": "REGRESSION_CHANNEL",
            "model_profile_code": profile["profile_code"],
            "short_window": int(config.get("short_window") or 20),
            "medium_window": int(config.get("medium_window") or 60),
            "trend_window": int(config.get("trend_window") or 120),
            "minimum_trend_duration": int(config.get("minimum_trend_duration") or 20),
            "channel_multiplier": float(config.get("channel_multiplier") or 2.0),
            "minimum_break_distance": float(config.get("minimum_break_distance") or 0.15),
            "minimum_break_persistence": int(config.get("minimum_break_persistence") or 2),
            "reversal_persistence": int(config.get("reversal_persistence") or 3),
            "false_break_window": int(config.get("false_break_window") or 5),
            "minimum_trend_strength": float(config.get("minimum_trend_strength") or 1.0),
            "minimum_r_squared": float(config.get("minimum_r_squared") or 0.18),
            "volatility_window": int(config.get("volatility_window") or 20),
            "is_active": 1,
        }

    def _validated_preview_configuration(self, configuration: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
        if not configuration:
            return {}
        data_count = int(catalog.get("data_count") or 0)
        patch: dict[str, Any] = {}
        int_fields = ("short_window", "medium_window", "trend_window", "minimum_break_persistence", "false_break_window", "reversal_persistence")
        for key in int_fields:
            if key in configuration and configuration[key] not in {None, ""}:
                patch[key] = int(configuration[key])
        if "channel_multiplier" in configuration and configuration["channel_multiplier"] not in {None, ""}:
            patch["channel_multiplier"] = float(configuration["channel_multiplier"])
        short_window = int(patch.get("short_window") or 20)
        medium_window = int(patch.get("medium_window") or 60)
        trend_window = int(patch.get("trend_window") or 120)
        channel_multiplier = float(patch.get("channel_multiplier") or 2.0)
        break_persistence = int(patch.get("minimum_break_persistence") or 2)
        false_break_window = int(patch.get("false_break_window") or 5)
        reversal_persistence = int(patch.get("reversal_persistence") or 3)
        if short_window < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="short_window must be at least 2")
        if medium_window < short_window:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="medium_window must be greater than or equal to short_window")
        if trend_window < 5:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trend_window must be at least 5")
        if data_count and trend_window > data_count:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trend_window must be less than or equal to data count")
        if channel_multiplier < 0.5 or channel_multiplier > 5:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="channel_multiplier must be between 0.5 and 5.0")
        if break_persistence < 1 or break_persistence > trend_window:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="minimum_break_persistence must be between 1 and trend_window")
        if false_break_window < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="false_break_window must be at least 1")
        if reversal_persistence < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reversal_persistence must be at least 1")
        return patch

    @staticmethod
    def _default_preview_period(frequency: str) -> str:
        frequency = frequency.upper()
        if frequency == "MONTHLY":
            return "3Y"
        if frequency == "WEEKLY":
            return "1Y"
        return "3M"

    def _existing_single_signal(self, item_type: str, item_code: str, profile_code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT d.id, d.signal_code, d.signal_name, d.status
                FROM market_signal_definitions d
                JOIN market_signal_conditions c ON c.signal_definition_id = d.id
                LEFT JOIN market_signal_trend_models tm ON tm.signal_definition_id = d.id
                WHERE c.item_type = :item_type
                  AND c.item_code = :item_code
                  AND COALESCE(tm.model_profile_code, :profile_code) = :profile_code
                  AND d.signal_type IN ('ATOMIC', 'SINGLE_INDICATOR')
                ORDER BY d.id
                LIMIT 1
                """
            ),
            {"item_type": item_type, "item_code": item_code, "profile_code": profile_code},
        ).mappings().first()
        return dict(row) if row else None

    def _create_single_indicator_draft_from_data(self, data: dict[str, Any]) -> dict[str, Any]:
        item_type = str(data.get("item_type") or "INDICATOR").upper()
        item_code = str(data.get("item_code") or "").upper()
        if not item_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="item_code is required")
        catalog = self._catalog_lookup(item_type, item_code)
        if not catalog:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"catalog item not found: {item_type} {item_code}")
        if catalog["signal_readiness"] == "DATA_INSUFFICIENT":
            return {"created": False, "item_type": item_type, "item_code": item_code, "reason": "DATA_INSUFFICIENT"}
        profile_code = str(data.get("profile_code") or catalog["recommended_profile_code"])
        existing = self._existing_single_signal(item_type, item_code, profile_code)
        if existing:
            return {"created": False, "item_type": item_type, "item_code": item_code, "profile_code": profile_code, "reason": "DUPLICATE_DRAFT_OR_SIGNAL", "existing_signal": existing}
        profile = self._profile_by_code(profile_code)
        configuration_patch = self._validated_preview_configuration(data.get("configuration") or {}, catalog)
        signal_code = f"SINGLE_{profile_code}_{item_type}_{item_code}".upper()
        payload = {
            "signal_code": signal_code,
            "signal_name": f"{catalog['item_name']} 단일 지표 시그널",
            "description": f"{catalog['item_name']}에 {profile['profile_name']} 모델을 적용한 DRAFT입니다.",
            "category": catalog.get("category_group") or catalog.get("category"),
            "signal_type": "ATOMIC",
            "horizon": "MEDIUM",
            "status": "DRAFT",
            "interpretation_direction": "MIXED",
            "phenomenon_template": f"{catalog['item_name']} 추세 전환",
            "process_template": catalog.get("recommended_profile_reason"),
            "result_template": "DRAFT 검증 후 사용자가 활성화할 수 있습니다.",
            "persistence_periods": 2,
            "cooldown_periods": 1,
            "minimum_data_quality": 50,
            "conditions": [
                {
                    "condition_group": "A",
                    "condition_role": "TRIGGER",
                    "item_type": item_type,
                    "item_code": item_code,
                    "transform_type": "TREND_STATE",
                    "window_size": 20,
                    "comparison_operator": "!=",
                    "threshold_type": "ABSOLUTE",
                    "threshold_value": 0,
                    "threshold_secondary": None,
                    "weight": 20,
                    "is_required": True,
                    "sort_order": 1,
                }
            ],
            "change_reason": f"Created from catalog with profile {profile_code}",
        }
        created = self.upsert_signal(payload)
        model = self._model_from_profile(profile, item_type=item_type, item_code=item_code)
        model.update(configuration_patch)
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_signal_trend_models
                (signal_definition_id, item_type, item_code, model_type, model_profile_code, short_window, medium_window, trend_window,
                 minimum_trend_duration, channel_multiplier, minimum_break_distance, minimum_break_persistence,
                 reversal_persistence, false_break_window, minimum_trend_strength, minimum_r_squared, volatility_window, is_active)
                VALUES (:signal_definition_id, :item_type, :item_code, :model_type, :model_profile_code, :short_window, :medium_window, :trend_window,
                        :minimum_trend_duration, :channel_multiplier, :minimum_break_distance, :minimum_break_persistence,
                        :reversal_persistence, :false_break_window, :minimum_trend_strength, :minimum_r_squared, :volatility_window, 1)
                """
            ),
            {**model, "signal_definition_id": created["id"]},
        )
        self.db.commit()
        return {"created": True, "item_type": item_type, "item_code": item_code, "profile_code": profile_code, "signal": created}

    def _ensure_evidence_sources(self) -> None:
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_signal_evidence_sources
                (source_code, source_name, source_type, item_type, item_code, provider, evidence_group_code)
                SELECT i.indicator_code, COALESCE(i.indicator_name, i.indicator_code), 'INDICATOR', 'INDICATOR', i.indicator_code,
                       m.provider, COALESCE(i.category, 'MARKET')
                FROM market_indicators i
                LEFT JOIN market_indicator_provider_mappings m ON m.indicator_code = i.indicator_code AND m.is_enabled = 1
                WHERE i.is_active = 1
                """
            )
        )
        self.db.commit()

    def _trend_model_rows(self) -> list[Any]:
        rows = self.db.execute(
            text(
                """
                SELECT tm.*,
                       d.status AS definition_status,
                       d.current_version,
                       d.validation_status,
                       d.validation_period_years,
                       d.validation_completed_at,
                       d.activation_ready,
                       d.activated_at,
                       d.deactivated_at,
                       COALESCE(i.indicator_name, ix.index_name, tm.item_code) AS indicator_name,
                       COALESCE(i.category, ix.category) AS category,
                       COALESCE(i.data_frequency, 'DAILY') AS data_frequency,
                       COALESCE(i.unit_label, ix.currency) AS unit_label,
                       COALESCE(m.provider, ix.provider) AS provider,
                       COALESCE(m.provider_symbol, ix.provider_symbol) AS provider_symbol
                FROM market_signal_trend_models tm
                LEFT JOIN market_signal_definitions d ON d.id = tm.signal_definition_id
                LEFT JOIN market_indicators i ON i.indicator_code = tm.item_code AND tm.item_type = 'INDICATOR'
                LEFT JOIN market_indicator_provider_mappings m ON m.indicator_code = tm.item_code AND m.is_enabled = 1 AND tm.item_type = 'INDICATOR'
                LEFT JOIN market_indexes ix ON ix.index_code = tm.item_code AND tm.item_type = 'INDEX'
                WHERE tm.is_active = 1
                ORDER BY tm.item_type, tm.item_code, COALESCE(tm.model_profile_code, 'MARKET_PRICE_TREND'), tm.id
                """
            )
        ).mappings().all()
        deduped: list[Any] = []
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            key = (str(row["item_type"]), str(row["item_code"]), str(row.get("model_profile_code") or "MARKET_PRICE_TREND"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    def _trend_model_row(self, model_id: int) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                SELECT tm.*,
                       d.status AS definition_status,
                       d.current_version,
                       d.validation_status,
                       d.validation_period_years,
                       d.validation_completed_at,
                       d.activation_ready,
                       d.activated_at,
                       d.deactivated_at,
                       COALESCE(i.indicator_name, ix.index_name, tm.item_code) AS indicator_name,
                       COALESCE(i.category, ix.category) AS category,
                       COALESCE(i.data_frequency, 'DAILY') AS data_frequency,
                       COALESCE(i.unit_label, ix.currency) AS unit_label,
                       COALESCE(m.provider, ix.provider) AS provider,
                       COALESCE(m.provider_symbol, ix.provider_symbol) AS provider_symbol
                FROM market_signal_trend_models tm
                LEFT JOIN market_signal_definitions d ON d.id = tm.signal_definition_id
                LEFT JOIN market_indicators i ON i.indicator_code = tm.item_code AND tm.item_type = 'INDICATOR'
                LEFT JOIN market_indicator_provider_mappings m ON m.indicator_code = tm.item_code AND m.is_enabled = 1 AND tm.item_type = 'INDICATOR'
                LEFT JOIN market_indexes ix ON ix.index_code = tm.item_code AND tm.item_type = 'INDEX'
                WHERE tm.id = :id
                """
            ),
            {"id": model_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="single indicator trend model not found")
        return dict(row)

    def _single_indicator_item(self, row: dict[str, Any], *, observation_date: str, include_chart: bool) -> dict[str, Any]:
        diagnostic = self._trend_diagnostic(row["item_type"], row["item_code"], observation_date, model=row)
        item = {
            "id": row["id"],
            "signal_definition_id": row.get("signal_definition_id"),
            "signal_level": "SINGLE_INDICATOR",
            "user_label": "단일 지표 시그널",
            "item_type": row["item_type"],
            "item_code": row["item_code"],
            "item_name": row.get("indicator_name") or row["item_code"],
            "category": row.get("category"),
            "frequency": row.get("data_frequency"),
            "unit_label": row.get("unit_label"),
            "provider": row.get("provider"),
            "provider_symbol": row.get("provider_symbol"),
            "model_profile_code": row.get("model_profile_code") or "MARKET_PRICE_TREND",
            "rule_status": row.get("definition_status") or ("ACTIVE" if int(row.get("is_active") or 0) else "INACTIVE"),
            "current_version": row.get("current_version") or 1,
            "validation_status": row.get("validation_status") or "UNVALIDATED",
            "validation_period_years": row.get("validation_period_years"),
            "validation_completed_at": row.get("validation_completed_at"),
            "activation_ready": bool(row.get("activation_ready") or 0),
            "activated_at": row.get("activated_at"),
            "deactivated_at": row.get("deactivated_at"),
            "evaluation_status": diagnostic["trend_health"],
            "trend_state": diagnostic["trend_state"],
            "trend_strength": diagnostic["trend_strength"],
            "latest_value": diagnostic["latest_value"],
            "latest_value_date": diagnostic["observation_date"],
            "diagnostic": {key: value for key, value in diagnostic.items() if key != "series"},
        }
        if include_chart:
            item["series"] = diagnostic["series"]
        return item

    def _composite_item(self, row: dict[str, Any], *, include_conditions: bool) -> dict[str, Any]:
        item = self._definition_item(row, include_conditions=include_conditions)
        item["signal_level"] = "COMPOSITE_INDICATOR"
        item["user_label"] = "복합 지표 시그널"
        item["relation_type"] = item.get("relation_type") or "CONDITIONAL_RELATION"
        item["confirmation_window"] = int(item.get("confirmation_window") or 5)
        item["minimum_confirm_count"] = int(item.get("minimum_confirm_count") or 1)
        if include_conditions:
            for condition in item["conditions"]:
                if condition["condition_role"] == "REQUIRED":
                    condition["display_role"] = "TRIGGER"
        return item

    def _phenomenon_item(self, row: dict[str, Any], *, observation_date: str, evaluate_now: bool) -> dict[str, Any]:
        evaluation = self._evaluate_signal(row, observation_date=observation_date, save=False) if evaluate_now else None
        status_map = {
            "ACTIVE": "CONFIRMED",
            "STRENGTHENING": "STRENGTHENING",
            "WEAKENING": "WEAKENING",
            "WATCH": "CANDIDATE",
            "RELEASED": "RELEASED",
            "DATA_INSUFFICIENT": "DATA_INSUFFICIENT",
            "INACTIVE": "NOT_EVALUATED",
        }
        evaluation_status = status_map.get(str(evaluation.get("state") if evaluation else "NOT_EVALUATED"), "NOT_EVALUATED")
        trigger_evidence = list(evaluation.get("evidence", [])) if evaluation else []
        confirm_evidence = [item for item in trigger_evidence if str(item.get("role") or "").upper() == "CONFIRM"]
        trigger_only = [item for item in trigger_evidence if str(item.get("role") or "").upper() in {"REQUIRED", "TRIGGER"}]
        opposing = list(evaluation.get("opposing_evidence", [])) if evaluation else []
        missing = list(evaluation.get("missing_data", [])) if evaluation else []
        return {
            "id": row["id"],
            "phenomenon_code": row.get("phenomenon_code") or row.get("signal_code"),
            "phenomenon_name": row.get("signal_name"),
            "signal_level": "PHENOMENON",
            "user_label": "객관적 현상",
            "rule_status": row.get("status"),
            "evaluation_status": evaluation_status,
            "fulfillment_score": evaluation.get("score") if evaluation else None,
            "observation_date": observation_date,
            "trigger_date": observation_date if trigger_only else None,
            "first_confirm_date": observation_date if confirm_evidence else None,
            "confirmation_elapsed_periods": 0 if confirm_evidence else None,
            "persistence_periods": row.get("persistence_periods"),
            "trigger_evidence": trigger_only,
            "confirm_evidence": confirm_evidence,
            "context_evidence": [item for item in trigger_evidence if str(item.get("role") or "").upper() == "CONTEXT"],
            "opposing_evidence": opposing,
            "invalidation_evidence": [item for item in trigger_evidence if str(item.get("role") or "").upper() == "INVALIDATION"],
            "missing_conditions": missing,
            "timeline": self._phenomenon_timeline(int(row["id"])),
            "next_checks": self._next_checks(row, missing),
            "data_quality_score": evaluation.get("data_quality_score") if evaluation else None,
            "applied_rule_version": row.get("current_version") or 1,
            "cards": {
                "observed_facts": trigger_only + confirm_evidence,
                "rule_interpretation": {
                    "phenomenon": evaluation.get("phenomenon_text") if evaluation else row.get("phenomenon_template"),
                    "process": evaluation.get("process_text") if evaluation else row.get("process_template"),
                    "result": evaluation.get("result_text") if evaluation else row.get("result_template"),
                },
                "gpt_auxiliary_diagnosis": "GPT 진단은 별도 요청 시 보조 의견으로만 생성됩니다.",
                "uncertainty": {
                    "opposing_count": len(opposing),
                    "missing_count": len(missing),
                    "data_quality_score": evaluation.get("data_quality_score") if evaluation else None,
                },
            },
        }

    def _composite_relation_diagnostic(self, signal: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
        trigger = [item for item in evaluation.get("evidence", []) if str(item.get("role") or "").upper() in {"REQUIRED", "TRIGGER"}]
        confirm = [item for item in evaluation.get("evidence", []) if str(item.get("role") or "").upper() == "CONFIRM"]
        context = [item for item in evaluation.get("evidence", []) if str(item.get("role") or "").upper() == "CONTEXT"]
        invalidation = [item for item in evaluation.get("evidence", []) if str(item.get("role") or "").upper() == "INVALIDATION"]
        minimum_confirm = int(signal.get("minimum_confirm_count") or 1)
        false_start = bool(trigger and len(confirm) < minimum_confirm and evaluation.get("state") in {"WATCH", "INACTIVE"})
        return {
            "relation_type": signal.get("relation_type") or "CONDITIONAL_RELATION",
            "trigger_evidence_count": len(trigger),
            "confirm_evidence_count": len(confirm),
            "context_evidence_count": len(context),
            "opposing_evidence_count": len(evaluation.get("opposing_evidence", [])),
            "invalidation_evidence_count": len(invalidation),
            "confirmation_window": int(signal.get("confirmation_window") or 5),
            "minimum_confirm_count": minimum_confirm,
            "false_start": false_start,
            "duplicate_evidence_groups": self._duplicate_condition_keys(int(signal["id"])),
        }

    def _trend_diagnostic(self, item_type: str, item_code: str, observation_date: str, *, model: dict[str, Any] | None = None, source_series: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        model = model or {}
        trend_window = int(model.get("trend_window") or 120)
        short_window = int(model.get("short_window") or 20)
        medium_window = int(model.get("medium_window") or 60)
        channel_multiplier = float(model.get("channel_multiplier") or 2.0)
        min_strength = float(model.get("minimum_trend_strength") or 1.0)
        min_r2 = float(model.get("minimum_r_squared") or 0.18)
        min_duration = int(model.get("minimum_trend_duration") or 20)
        break_distance = float(model.get("minimum_break_distance") or 0.15)
        break_persistence = int(model.get("minimum_break_persistence") or 2)
        false_break_window = int(model.get("false_break_window") or 5)
        limit = max(trend_window + medium_window + false_break_window + 20, 180)
        series = source_series if source_series is not None else self._series(item_type, item_code, observation_date, limit=limit)
        values = [row["value"] for row in series]
        if len(values) < max(8, min(trend_window, min_duration)):
            return self._empty_trend_result(item_type, item_code, observation_date, series)

        sample_count = min(trend_window, len(values))
        analysis_start_index = len(values) - sample_count
        sample = values[-sample_count:]
        regression = self._linear_regression(sample)
        last = sample[-1]
        mean_abs = max(abs(self._mean(sample) or 0), 1e-9)
        normalized_slope = (regression["slope"] / mean_abs) * len(sample) * 100
        trend_strength = abs(normalized_slope) * max(float(regression["r_squared"]), 0.01)
        short_slope = self._window_slope(values, short_window)
        medium_slope = self._window_slope(values, medium_window)
        upper = regression["last_center"] + channel_multiplier * regression["residual_stddev"]
        lower = regression["last_center"] - channel_multiplier * regression["residual_stddev"]
        channel_width = upper - lower
        channel_position = None if math.isclose(channel_width, 0) else (last - lower) / channel_width
        up_ratio = self._recent_direction_ratio(values[-min(short_window, len(values)) :], upward=True)
        down_ratio = self._recent_direction_ratio(values[-min(short_window, len(values)) :], upward=False)
        trend_state = "SIDEWAYS"
        if regression["r_squared"] < min_r2 and trend_strength >= min_strength:
            trend_state = "UNSTABLE"
        elif normalized_slope >= min_strength and regression["r_squared"] >= min_r2:
            trend_state = "UP_TREND"
        elif normalized_slope <= -min_strength and regression["r_squared"] >= min_r2:
            trend_state = "DOWN_TREND"
        elif trend_strength < min_strength:
            trend_state = "SIDEWAYS"

        break_up = last > upper + break_distance * max(regression["residual_stddev"], 1e-9)
        break_down = last < lower - break_distance * max(regression["residual_stddev"], 1e-9)
        outside_flags = self._channel_outside_flags(sample, regression, channel_multiplier, break_distance)
        break_confirmed_up = self._tail_count(outside_flags, "UP") >= break_persistence
        break_confirmed_down = self._tail_count(outside_flags, "DOWN") >= break_persistence
        false_break_up = self._false_break(outside_flags, "UP", false_break_window)
        false_break_down = self._false_break(outside_flags, "DOWN", false_break_window)
        reversal_up = trend_state == "DOWN_TREND" and break_confirmed_up and (short_slope or 0) > 0 and (medium_slope or 0) >= 0
        reversal_down = trend_state == "UP_TREND" and break_confirmed_down and (short_slope or 0) < 0 and (medium_slope or 0) <= 0
        trend_resumed_up = trend_state == "UP_TREND" and false_break_down and (short_slope or 0) > 0
        trend_resumed_down = trend_state == "DOWN_TREND" and false_break_up and (short_slope or 0) < 0
        trend_health = "TREND_INTACT"
        if false_break_up or false_break_down:
            trend_health = "FALSE_BREAK"
        if trend_resumed_up or trend_resumed_down:
            trend_health = "TREND_RESUMED"
        if break_up or break_down:
            trend_health = "BREAK_CANDIDATE"
        if break_confirmed_up or break_confirmed_down:
            trend_health = "BREAK_CONFIRMED"
        if reversal_up or reversal_down:
            trend_health = "REVERSAL_CONFIRMED"
        if trend_state in {"UNSTABLE", "SIDEWAYS"} and trend_health == "TREND_INTACT":
            trend_health = "TREND_WEAKENING"

        analysis_series = self._channel_series(series[analysis_start_index:], regression, channel_multiplier)
        chart_series: list[dict[str, Any]] = []
        for idx, row in enumerate(series):
            chart_row: dict[str, Any] = {
                "date": row["date"],
                "value": row["value"],
                "is_trend_analysis_region": idx >= analysis_start_index,
                "is_trend_analysis_start": idx == analysis_start_index,
            }
            if idx >= analysis_start_index:
                chart_row.update(analysis_series[idx - analysis_start_index])
            chart_series.append(chart_row)
        return {
            "item_type": item_type,
            "item_code": item_code,
            "observation_date": series[-1]["date"],
            "display_range_start": series[0]["date"],
            "display_range_end": series[-1]["date"],
            "display_observation_count": len(series),
            "trend_analysis_start": series[analysis_start_index]["date"],
            "trend_analysis_end": series[-1]["date"],
            "trend_analysis_observation_count": sample_count,
            "trend_analysis_uses_full_display": analysis_start_index == 0,
            "latest_value": round(last, 6),
            "trend_state": trend_state,
            "trend_health": trend_health,
            "regression_slope": round(regression["slope"], 8),
            "normalized_slope": round(normalized_slope, 6),
            "r_squared": round(regression["r_squared"], 6),
            "trend_strength": round(trend_strength, 6),
            "short_slope": None if short_slope is None else round(short_slope, 8),
            "medium_slope": None if medium_slope is None else round(medium_slope, 8),
            "moving_average_alignment": self._ma_alignment(values, short_window, medium_window),
            "recent_up_ratio": round(up_ratio, 4),
            "recent_down_ratio": round(down_ratio, 4),
            "trend_duration": self._trend_duration(values, normalized_slope),
            "channel_position": None if channel_position is None else round(channel_position, 6),
            "channel_center": round(regression["last_center"], 6),
            "channel_upper": round(upper, 6),
            "channel_lower": round(lower, 6),
            "channel_break_distance": round(max(last - upper, lower - last, 0), 6),
            "trend_break_up": break_up,
            "trend_break_down": break_down,
            "break_confirmed_up": break_confirmed_up,
            "break_confirmed_down": break_confirmed_down,
            "false_break_up": false_break_up,
            "false_break_down": false_break_down,
            "reversal_confirmed_up": reversal_up,
            "reversal_confirmed_down": reversal_down,
            "trend_resumed_up": trend_resumed_up,
            "trend_resumed_down": trend_resumed_down,
            "series": chart_series,
        }

    def _empty_trend_result(self, item_type: str, item_code: str, observation_date: str, series: list[dict[str, Any]]) -> dict[str, Any]:
        latest = series[-1] if series else {"date": observation_date, "value": None}
        chart_series = [
            {
                "date": row["date"],
                "value": row["value"],
                "is_trend_analysis_region": False,
                "is_trend_analysis_start": False,
            }
            for row in series
        ]
        return {
            "item_type": item_type,
            "item_code": item_code,
            "observation_date": latest["date"],
            "display_range_start": series[0]["date"] if series else None,
            "display_range_end": latest["date"],
            "display_observation_count": len(series),
            "trend_analysis_start": None,
            "trend_analysis_end": None,
            "trend_analysis_observation_count": 0,
            "trend_analysis_uses_full_display": False,
            "latest_value": latest["value"],
            "trend_state": "INSUFFICIENT_DATA",
            "trend_health": "DATA_INSUFFICIENT",
            "regression_slope": None,
            "normalized_slope": None,
            "r_squared": None,
            "trend_strength": 0,
            "short_slope": None,
            "medium_slope": None,
            "moving_average_alignment": "UNKNOWN",
            "recent_up_ratio": 0,
            "recent_down_ratio": 0,
            "trend_duration": 0,
            "channel_position": None,
            "channel_center": None,
            "channel_upper": None,
            "channel_lower": None,
            "channel_break_distance": None,
            "trend_break_up": False,
            "trend_break_down": False,
            "break_confirmed_up": False,
            "break_confirmed_down": False,
            "false_break_up": False,
            "false_break_down": False,
            "reversal_confirmed_up": False,
            "reversal_confirmed_down": False,
            "trend_resumed_up": False,
            "trend_resumed_down": False,
            "series": chart_series,
        }

    def _linear_regression(self, values: list[float]) -> dict[str, float]:
        count = len(values)
        xs = list(range(count))
        x_mean = self._mean([float(x) for x in xs]) or 0
        y_mean = self._mean(values) or 0
        denominator = sum((x - x_mean) ** 2 for x in xs)
        slope = 0.0 if denominator == 0 else sum((x - x_mean) * (value - y_mean) for x, value in zip(xs, values)) / denominator
        intercept = y_mean - slope * x_mean
        centers = [intercept + slope * x for x in xs]
        residuals = [value - center for value, center in zip(values, centers)]
        ss_total = sum((value - y_mean) ** 2 for value in values)
        ss_residual = sum(residual ** 2 for residual in residuals)
        r_squared = 0.0 if ss_total == 0 else max(0.0, min(1.0, 1 - ss_residual / ss_total))
        residual_stddev = statistics.pstdev(residuals) if len(residuals) >= 2 else 0.0
        return {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "residual_stddev": residual_stddev,
            "last_center": centers[-1],
        }

    def _window_slope(self, values: list[float], window: int) -> float | None:
        if len(values) < max(3, window):
            return None
        return self._linear_regression(values[-window:])["slope"]

    def _recent_direction_ratio(self, values: list[float], *, upward: bool) -> float:
        if len(values) < 2:
            return 0.0
        total = len(values) - 1
        count = sum(1 for idx in range(1, len(values)) if (values[idx] > values[idx - 1] if upward else values[idx] < values[idx - 1]))
        return count / total

    def _ma_alignment(self, values: list[float], short_window: int, medium_window: int) -> str:
        short_ma = self._mean(values[-short_window:]) if len(values) >= short_window else None
        medium_ma = self._mean(values[-medium_window:]) if len(values) >= medium_window else None
        if short_ma is None or medium_ma is None:
            return "UNKNOWN"
        if short_ma > medium_ma:
            return "SHORT_ABOVE_MEDIUM"
        if short_ma < medium_ma:
            return "SHORT_BELOW_MEDIUM"
        return "FLAT"

    def _trend_duration(self, values: list[float], normalized_slope: float) -> int:
        upward = normalized_slope >= 0
        return self._consecutive(values, upward=upward) + 1

    def _channel_outside_flags(self, sample: list[float], regression: dict[str, float], multiplier: float, break_distance: float) -> list[str | None]:
        flags: list[str | None] = []
        residual = max(regression["residual_stddev"], 1e-9)
        for idx, value in enumerate(sample):
            center = regression["intercept"] + regression["slope"] * idx
            upper = center + multiplier * residual
            lower = center - multiplier * residual
            if value > upper + break_distance * residual:
                flags.append("UP")
            elif value < lower - break_distance * residual:
                flags.append("DOWN")
            else:
                flags.append(None)
        return flags

    @staticmethod
    def _tail_count(flags: list[str | None], target: str) -> int:
        count = 0
        for flag in reversed(flags):
            if flag == target:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _false_break(flags: list[str | None], target: str, window: int) -> bool:
        recent = flags[-max(window, 1) :]
        return bool(recent and recent[-1] is None and target in recent[:-1])

    def _channel_series(self, source: list[dict[str, Any]], regression: dict[str, float], multiplier: float) -> list[dict[str, Any]]:
        residual = regression["residual_stddev"]
        rows = []
        for idx, row in enumerate(source):
            center = regression["intercept"] + regression["slope"] * idx
            rows.append(
                {
                    "date": row["date"],
                    "value": row["value"],
                    "center": round(center, 6),
                    "upper": round(center + multiplier * residual, 6),
                    "lower": round(center - multiplier * residual, 6),
                }
            )
        return rows

    def _save_trend_episode_marker(self, signal_id: int, item_code: str, observation_date: str, diagnostic: dict[str, Any]) -> None:
        if diagnostic["trend_health"] not in {"BREAK_CANDIDATE", "BREAK_CONFIRMED", "REVERSAL_CONFIRMED", "FALSE_BREAK", "TREND_RESUMED"}:
            return
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_signal_events
                (signal_definition_id, event_date, previous_state, new_state, previous_score, new_score, event_type, summary)
                VALUES (:signal_definition_id, :event_date, NULL, :new_state, NULL, :new_score, :event_type, :summary)
                """
            ),
            {
                "signal_definition_id": signal_id,
                "event_date": observation_date,
                "new_state": diagnostic["trend_health"],
                "new_score": float(diagnostic.get("trend_strength") or 0),
                "event_type": f"SINGLE_{diagnostic['trend_health']}",
                "summary": f"{item_code} {diagnostic['trend_health']} ({diagnostic.get('trend_state')})",
            },
        )
        self.db.commit()

    def _item_dates(self, item_type: str, item_code: str, *, years: int) -> list[str]:
        if item_type.upper() == "INDEX":
            sql = """
                SELECT DISTINCT price_date
                FROM market_index_daily_prices
                WHERE index_code = :code AND price_date >= date('now', :years)
                ORDER BY price_date
            """
            column = "price_date"
        else:
            sql = """
                SELECT DISTINCT value_date
                FROM market_indicator_values
                WHERE indicator_code = :code AND value_date >= date('now', :years)
                ORDER BY value_date
            """
            column = "value_date"
        rows = self.db.execute(text(sql), {"code": item_code, "years": f"-{max(years, 1)} years"}).mappings().all()
        return [str(row[column]) for row in rows]

    def _phenomenon_timeline(self, signal_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT event_date, previous_state, new_state, event_type, summary
                FROM market_signal_events
                WHERE signal_definition_id = :id
                ORDER BY event_date DESC, id DESC
                LIMIT 12
                """
            ),
            {"id": signal_id},
        ).mappings().all()
        return [dict(row) for row in reversed(rows)]

    @staticmethod
    def _next_checks(signal: dict[str, Any], missing: list[dict[str, Any]]) -> list[str]:
        if missing:
            return [f"{item.get('item_code')} 데이터 확보 후 재평가" for item in missing[:5]]
        return [
            f"{signal.get('signal_code')} 확인 조건의 지속성 점검",
            "반대 증거와 무효화 조건 동시 점검",
        ]

    def _upsert_episode(self, signal: dict[str, Any], item: dict[str, Any]) -> None:
        trigger_date = item.get("trigger_date") or item.get("observation_date")
        timeline = item.get("timeline") or []
        self.db.execute(
            text(
                """
                INSERT INTO market_signal_episodes
                (phenomenon_definition_id, phenomenon_code, trigger_date, first_confirm_date, state, peak_score, latest_score,
                 data_quality_score, applied_rule_version, timeline_json)
                VALUES (:phenomenon_definition_id, :phenomenon_code, :trigger_date, :first_confirm_date, :state, :peak_score, :latest_score,
                        :data_quality_score, :applied_rule_version, :timeline_json)
                ON CONFLICT(phenomenon_definition_id, trigger_date, applied_rule_version) DO UPDATE SET
                    state = excluded.state,
                    peak_score = MAX(COALESCE(peak_score, 0), COALESCE(excluded.peak_score, 0)),
                    latest_score = excluded.latest_score,
                    data_quality_score = excluded.data_quality_score,
                    timeline_json = excluded.timeline_json,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "phenomenon_definition_id": signal["id"],
                "phenomenon_code": item["phenomenon_code"],
                "trigger_date": trigger_date,
                "first_confirm_date": item.get("first_confirm_date"),
                "state": item["evaluation_status"],
                "peak_score": item.get("fulfillment_score"),
                "latest_score": item.get("fulfillment_score"),
                "data_quality_score": item.get("data_quality_score"),
                "applied_rule_version": item.get("applied_rule_version") or 1,
                "timeline_json": json.dumps(timeline, ensure_ascii=False, sort_keys=True),
            },
        )
        self.db.commit()

    def _episode_item(self, row: dict[str, Any]) -> dict[str, Any]:
        row["timeline"] = json.loads(row.pop("timeline_json") or "[]")
        return row

    @staticmethod
    def _json_columns(row: dict[str, Any], columns: tuple[str, ...]) -> dict[str, Any]:
        for column in columns:
            row[column.removesuffix("_json")] = json.loads(row.pop(column) or "{}")
        return row

    def _evaluate_signal(self, signal: dict[str, Any], *, observation_date: str, save: bool, conditions_override: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        conditions = conditions_override if conditions_override is not None else self._condition_rows(signal["id"])
        evidence = []
        opposing = []
        missing = []
        required_total = 0
        required_pass = 0
        confirm_pass = 0
        opposing_pass = 0
        score = 0.0
        max_data = len(conditions) or 1
        for condition in conditions:
            condition = dict(condition)
            role = str(condition["condition_role"]).upper()
            if role in {"REQUIRED", "TRIGGER"}:
                required_total += 1
            result = self._evaluate_condition(condition, observation_date)
            if result["missing"]:
                missing.append(result)
                continue
            passed = result["passed"]
            if role == "OPPOSING":
                if passed:
                    opposing_pass += 1
                    opposing.append(result)
                    score -= abs(float(condition["weight"]))
                else:
                    score += min(abs(float(condition["weight"])) * 0.25, 3)
                continue
            if role == "INVALIDATION":
                if passed:
                    opposing_pass += 1
                    opposing.append(result)
                    score -= abs(float(condition["weight"])) * 1.5
                continue
            if role == "CONTEXT":
                if passed:
                    evidence.append(result)
                    score += float(condition["weight"]) * 0.5
                continue
            if passed:
                evidence.append(result)
                score += float(condition["weight"])
                if role in {"REQUIRED", "TRIGGER"}:
                    required_pass += 1
                elif role == "CONFIRM":
                    confirm_pass += 1
        data_quality = round(((max_data - len(missing)) / max_data) * 100, 2)
        if missing and data_quality < float(signal.get("minimum_data_quality") or 60):
            state = "DATA_INSUFFICIENT"
        elif required_total and required_pass < required_total:
            state = "WATCH" if score >= 40 else "INACTIVE"
        else:
            state = self._state_from_score(score)
        previous = self._previous_evaluation(signal["id"], observation_date)
        if previous and str(previous.get("state") or "") in {"ACTIVE", "STRENGTHENING", "WEAKENING"} and state in {"INACTIVE", "WATCH"}:
            state = "RELEASED"
        elif state == "ACTIVE" and previous:
            previous_state = str(previous.get("state") or "")
            previous_score = float(previous.get("score") or 0)
            if previous_state in {"ACTIVE", "STRENGTHENING", "WEAKENING"}:
                if score > previous_score + 5:
                    state = "STRENGTHENING"
                elif score < previous_score - 5:
                    state = "WEAKENING"
        item = {
            "signal_definition_id": signal["id"],
            "signal_code": signal.get("signal_code"),
            "signal_name": signal.get("signal_name"),
            "observation_date": observation_date,
            "state": state,
            "score": round(max(score, 0), 2),
            "previous_score": previous.get("score") if previous else None,
            "data_quality_score": data_quality,
            "required_pass_count": required_pass,
            "required_total_count": required_total,
            "confirm_pass_count": confirm_pass,
            "opposing_pass_count": opposing_pass,
            "phenomenon_text": signal.get("phenomenon_template"),
            "process_text": signal.get("process_template"),
            "result_text": signal.get("result_template"),
            "evidence": evidence,
            "opposing_evidence": opposing,
            "missing_data": missing,
        }
        if save:
            self._save_evaluation(item, previous)
        return item

    def _evaluate_condition(self, condition: dict[str, Any], observation_date: str) -> dict[str, Any]:
        series = self._series(condition["item_type"], condition["item_code"], observation_date, limit=max(int(condition["window_size"] or 20) + 260, 280))
        value = self._transform(condition["transform_type"], series, int(condition["window_size"] or 20))
        threshold = self._threshold(condition, series)
        passed = False if value is None or threshold is None else self._compare(value, str(condition["comparison_operator"]), threshold)
        return {
            "condition_id": condition.get("id"),
            "role": condition["condition_role"],
            "item_type": condition["item_type"],
            "item_code": condition["item_code"],
            "transform_type": condition["transform_type"],
            "window_size": condition["window_size"],
            "operator": condition["comparison_operator"],
            "threshold_type": condition["threshold_type"],
            "threshold_value": threshold,
            "value": value,
            "passed": passed,
            "weight": condition["weight"],
            "missing": value is None or threshold is None,
        }

    def _series(self, item_type: str, item_code: str, observation_date: str, *, limit: int) -> list[dict[str, Any]]:
        if item_type.upper() == "INDEX":
            sql = """
                SELECT price_date AS value_date, close_price AS value
                FROM market_index_daily_prices
                WHERE index_code = :code AND price_date <= :observation_date AND close_price IS NOT NULL
                ORDER BY price_date DESC
                LIMIT :limit
            """
        else:
            sql = """
                SELECT value_date, COALESCE(value, close_value) AS value
                FROM market_indicator_values
                WHERE indicator_code = :code AND value_date <= :observation_date AND COALESCE(value, close_value) IS NOT NULL
                ORDER BY value_date DESC
                LIMIT :limit
            """
        rows = self.db.execute(text(sql), {"code": item_code, "observation_date": observation_date, "limit": limit}).mappings().all()
        return list(reversed([{"date": row["value_date"], "value": float(row["value"])} for row in rows]))

    def _series_for_preview_period(self, item_type: str, item_code: str, observation_date: str, *, period: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        period = period.upper()
        end_date = date.fromisoformat(observation_date)
        days_by_period = {"1M": 31, "3M": 93, "6M": 186, "1Y": 365, "3Y": 365 * 3}
        if period == "ALL":
            start_date = None
            description = "전체 사용 가능 관측값"
        else:
            days = days_by_period.get(period, 93)
            start_date = end_date - timedelta(days=days)
            description = f"최근 {period}"
        if item_type.upper() == "INDEX":
            sql = """
                SELECT price_date AS value_date, close_price AS value
                FROM market_index_daily_prices
                WHERE index_code = :code
                  AND price_date <= :observation_date
                  AND (:start_date IS NULL OR price_date >= :start_date)
                  AND close_price IS NOT NULL
                ORDER BY price_date ASC
            """
        else:
            sql = """
                SELECT value_date, COALESCE(value, close_value) AS value
                FROM market_indicator_values
                WHERE indicator_code = :code
                  AND value_date <= :observation_date
                  AND (:start_date IS NULL OR value_date >= :start_date)
                  AND COALESCE(value, close_value) IS NOT NULL
                ORDER BY value_date ASC
            """
        rows = self.db.execute(
            text(sql),
            {"code": item_code, "observation_date": observation_date, "start_date": start_date.isoformat() if start_date else None},
        ).mappings().all()
        series = [{"date": row["value_date"], "value": float(row["value"])} for row in rows]
        if not series:
            series = self._series(item_type, item_code, observation_date, limit=1)
        range_start = series[0]["date"] if series else None
        range_end = series[-1]["date"] if series else observation_date
        return series, {
            "requested_period": period,
            "actual_period_type": "CALENDAR" if period != "ALL" else "ALL_AVAILABLE",
            "actual_period_description": f"{description} · {len(series)}개 관측값",
            "range_start": range_start,
            "range_end": range_end,
            "observation_count": len(series),
        }

    def _transform(self, transform: str, series: list[dict[str, Any]], window: int) -> float | None:
        transform = transform.upper()
        values = [row["value"] for row in series]
        if not values:
            return None
        last = values[-1]
        prev = values[-2] if len(values) >= 2 else None
        if transform == "RAW_VALUE":
            return last
        if transform in {"CHANGE", "MOM"}:
            return None if prev is None else last - prev
        if transform in {"CHANGE_RATE", "YOY"}:
            base_idx = -min(window, len(values) - 1) - 1 if transform == "YOY" and len(values) > window else -2
            base = values[base_idx] if len(values) >= abs(base_idx) else None
            return None if base in {None, 0} else ((last / base) - 1) * 100
        if transform == "MOVING_AVERAGE":
            return self._mean(values[-window:])
        if transform == "SLOPE":
            if len(values) < max(3, window):
                return None
            return (values[-1] - values[-window]) / window
        if transform == "TREND_DIRECTION":
            slope = self._transform("SLOPE", series, window)
            return None if slope is None else (1 if slope > 0 else -1 if slope < 0 else 0)
        if transform in {"TURN_UP", "TURN_DOWN"}:
            if len(values) < max(4, window):
                return None
            earlier = (values[-window // 2] - values[-window]) / max(window // 2, 1)
            recent = (values[-1] - values[-window // 2]) / max(window // 2, 1)
            if transform == "TURN_UP":
                return recent - min(earlier, 0)
            return max(earlier, 0) - recent
        if transform.startswith("ACCELERATING") or transform.startswith("DECELERATING"):
            if len(values) < max(4, window):
                return None
            half = max(window // 2, 1)
            earlier = (values[-half] - values[-window]) / half
            recent = (values[-1] - values[-half]) / half
            return recent - earlier
        if transform == "Z_SCORE":
            sample = values[-window:]
            stdev = statistics.pstdev(sample) if len(sample) >= 2 else 0
            return None if stdev == 0 else (last - self._mean(sample)) / stdev
        if transform == "PERCENTILE":
            sample = values[-window:]
            return (sum(1 for value in sample if value <= last) / len(sample)) * 100 if sample else None
        if transform == "DISTANCE_FROM_MA":
            ma = self._mean(values[-window:])
            return None if ma in {None, 0} else ((last / ma) - 1) * 100
        if transform == "N_PERIOD_HIGH":
            return 1 if last >= max(values[-window:]) else 0
        if transform == "N_PERIOD_LOW":
            return 1 if last <= min(values[-window:]) else 0
        if transform == "CONSECUTIVE_UP":
            return self._consecutive(values, upward=True)
        if transform == "CONSECUTIVE_DOWN":
            return self._consecutive(values, upward=False)
        if transform == "PERSISTENCE":
            return sum(1 for idx in range(max(1, len(values) - window + 1), len(values)) if values[idx] > values[idx - 1])
        if transform in {
            "TREND_STATE",
            "REGRESSION_SLOPE",
            "NORMALIZED_SLOPE",
            "TREND_STRENGTH",
            "TREND_DURATION",
            "CHANNEL_POSITION",
            "TREND_BREAK_UP",
            "TREND_BREAK_DOWN",
            "BREAK_CONFIRMED_UP",
            "BREAK_CONFIRMED_DOWN",
            "FALSE_BREAK_UP",
            "FALSE_BREAK_DOWN",
            "REVERSAL_CONFIRMED_UP",
            "REVERSAL_CONFIRMED_DOWN",
            "TREND_RESUMED_UP",
            "TREND_RESUMED_DOWN",
        }:
            sample = values[-min(max(window, 20), len(values)) :]
            if len(sample) < 8:
                return None
            regression = self._linear_regression(sample)
            mean_abs = max(abs(self._mean(sample) or 0), 1e-9)
            normalized_slope = (regression["slope"] / mean_abs) * len(sample) * 100
            trend_strength = abs(normalized_slope) * max(float(regression["r_squared"]), 0.01)
            upper = regression["last_center"] + 2.0 * regression["residual_stddev"]
            lower = regression["last_center"] - 2.0 * regression["residual_stddev"]
            last_value = sample[-1]
            break_up = last_value > upper
            break_down = last_value < lower
            flags = self._channel_outside_flags(sample, regression, 2.0, 0.15)
            confirmed_up = self._tail_count(flags, "UP") >= 2
            confirmed_down = self._tail_count(flags, "DOWN") >= 2
            false_up = self._false_break(flags, "UP", 5)
            false_down = self._false_break(flags, "DOWN", 5)
            if transform == "TREND_STATE":
                if normalized_slope > 1 and regression["r_squared"] >= 0.18:
                    return 1
                if normalized_slope < -1 and regression["r_squared"] >= 0.18:
                    return -1
                return 0
            if transform == "REGRESSION_SLOPE":
                return regression["slope"]
            if transform == "NORMALIZED_SLOPE":
                return normalized_slope
            if transform == "TREND_STRENGTH":
                return trend_strength
            if transform == "TREND_DURATION":
                return float(self._trend_duration(values, normalized_slope))
            if transform == "CHANNEL_POSITION":
                width = upper - lower
                return None if math.isclose(width, 0) else (last_value - lower) / width
            if transform == "TREND_BREAK_UP":
                return 1 if break_up else 0
            if transform == "TREND_BREAK_DOWN":
                return 1 if break_down else 0
            if transform == "BREAK_CONFIRMED_UP":
                return 1 if confirmed_up else 0
            if transform == "BREAK_CONFIRMED_DOWN":
                return 1 if confirmed_down else 0
            if transform == "FALSE_BREAK_UP":
                return 1 if false_up else 0
            if transform == "FALSE_BREAK_DOWN":
                return 1 if false_down else 0
            if transform == "REVERSAL_CONFIRMED_UP":
                return 1 if confirmed_up and (self._window_slope(values, max(3, window // 3)) or 0) > 0 else 0
            if transform == "REVERSAL_CONFIRMED_DOWN":
                return 1 if confirmed_down and (self._window_slope(values, max(3, window // 3)) or 0) < 0 else 0
            if transform == "TREND_RESUMED_UP":
                return 1 if false_down and normalized_slope > 0 else 0
            if transform == "TREND_RESUMED_DOWN":
                return 1 if false_up and normalized_slope < 0 else 0
        if transform in {"SPREAD", "RATIO", "RELATIVE_STRENGTH"}:
            return last
        if transform == "CORRELATION":
            return None
        if transform == "DIVERGENCE":
            slope = self._transform("SLOPE", series, window)
            return None if slope is None else -slope
        return None

    def _threshold(self, condition: dict[str, Any], series: list[dict[str, Any]]) -> float | None:
        threshold_value = condition.get("threshold_value")
        if threshold_value is None:
            return None
        threshold_type = str(condition.get("threshold_type") or "ABSOLUTE").upper()
        if threshold_type == "ABSOLUTE":
            return float(threshold_value)
        values = [row["value"] for row in series]
        if not values:
            return None
        if threshold_type == "PERCENTILE":
            sorted_values = sorted(values)
            idx = max(0, min(len(sorted_values) - 1, int(round((float(threshold_value) / 100) * (len(sorted_values) - 1)))))
            return float(sorted_values[idx])
        if threshold_type == "Z_SCORE":
            return float(threshold_value)
        return float(threshold_value)

    @staticmethod
    def _compare(value: float, operator: str, threshold: float) -> bool:
        if operator == ">":
            return value > threshold
        if operator == ">=":
            return value >= threshold
        if operator == "<":
            return value < threshold
        if operator == "<=":
            return value <= threshold
        if operator in {"=", "=="}:
            return math.isclose(value, threshold)
        if operator == "!=":
            return not math.isclose(value, threshold)
        return False

    @staticmethod
    def _state_from_score(score: float) -> str:
        if score >= 60:
            return "ACTIVE"
        if score >= 40:
            return "WATCH"
        return "INACTIVE"

    def _save_evaluation(self, item: dict[str, Any], previous: dict[str, Any] | None) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO market_signal_evaluations
                (signal_definition_id, observation_date, state, score, previous_score, data_quality_score,
                 required_pass_count, required_total_count, confirm_pass_count, opposing_pass_count,
                 phenomenon_text, process_text, result_text, evidence_json, opposing_evidence_json, missing_data_json)
                VALUES (:signal_definition_id, :observation_date, :state, :score, :previous_score, :data_quality_score,
                        :required_pass_count, :required_total_count, :confirm_pass_count, :opposing_pass_count,
                        :phenomenon_text, :process_text, :result_text, :evidence_json, :opposing_evidence_json, :missing_data_json)
                ON CONFLICT(signal_definition_id, observation_date) DO UPDATE SET
                    evaluated_at = CURRENT_TIMESTAMP,
                    state = excluded.state,
                    score = excluded.score,
                    previous_score = excluded.previous_score,
                    data_quality_score = excluded.data_quality_score,
                    required_pass_count = excluded.required_pass_count,
                    required_total_count = excluded.required_total_count,
                    confirm_pass_count = excluded.confirm_pass_count,
                    opposing_pass_count = excluded.opposing_pass_count,
                    phenomenon_text = excluded.phenomenon_text,
                    process_text = excluded.process_text,
                    result_text = excluded.result_text,
                    evidence_json = excluded.evidence_json,
                    opposing_evidence_json = excluded.opposing_evidence_json,
                    missing_data_json = excluded.missing_data_json
                """
            ),
            {
                **item,
                "evidence_json": json.dumps(item["evidence"], ensure_ascii=False, sort_keys=True),
                "opposing_evidence_json": json.dumps(item["opposing_evidence"], ensure_ascii=False, sort_keys=True),
                "missing_data_json": json.dumps(item["missing_data"], ensure_ascii=False, sort_keys=True),
            },
        )
        previous_state = previous.get("state") if previous else None
        if previous_state != item["state"] and item["state"] != "DATA_INSUFFICIENT" and (previous or item["state"] in {"WATCH", "ACTIVE", "STRENGTHENING", "WEAKENING"}):
            self._save_event(item, previous)
        self.db.commit()

    def _save_event(self, item: dict[str, Any], previous: dict[str, Any] | None) -> None:
        prev_state = previous.get("state") if previous else None
        event_type = "TRIGGERED"
        if item["state"] == "RELEASED":
            event_type = "RELEASED"
        elif item["state"] == "STRENGTHENING":
            event_type = "STRENGTHENED"
        elif item["state"] == "WEAKENING":
            event_type = "WEAKENED"
        elif prev_state in {"ACTIVE", "WEAKENING", "STRENGTHENING"} and item["state"] in {"INACTIVE", "WATCH"}:
            event_type = "RELEASED"
        elif prev_state in {"INACTIVE", "WATCH"} and item["state"] in {"ACTIVE", "STRENGTHENING"}:
            event_type = "TRIGGERED"
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_signal_events
                (signal_definition_id, event_date, previous_state, new_state, previous_score, new_score, event_type, summary)
                VALUES (:signal_definition_id, :event_date, :previous_state, :new_state, :previous_score, :new_score, :event_type, :summary)
                """
            ),
            {
                "signal_definition_id": item["signal_definition_id"],
                "event_date": item["observation_date"],
                "previous_state": prev_state,
                "new_state": item["state"],
                "previous_score": previous.get("score") if previous else None,
                "new_score": item["score"],
                "event_type": event_type,
                "summary": f"{item.get('signal_name')} {prev_state or '-'} -> {item['state']} ({item['score']})",
            },
        )

    def _definition_params(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "signal_code": str(data.get("signal_code") or "").upper(),
            "signal_name": data.get("signal_name"),
            "description": data.get("description"),
            "category": data.get("category"),
            "signal_type": str(data.get("signal_type") or "COMPOSITE").upper(),
            "horizon": str(data.get("horizon") or "MEDIUM").upper(),
            "status": str(data.get("status") or "DRAFT").upper(),
            "interpretation_direction": str(data.get("interpretation_direction") or "MIXED").upper(),
            "phenomenon_template": data.get("phenomenon_template"),
            "process_template": data.get("process_template"),
            "result_template": data.get("result_template"),
            "persistence_periods": int(data.get("persistence_periods") or 1),
            "cooldown_periods": int(data.get("cooldown_periods") or 0),
            "minimum_data_quality": float(data.get("minimum_data_quality") or 60),
        }

    def _insert_condition(self, signal_id: int, condition: dict[str, Any], order: int) -> None:
        transform = str(condition.get("transform_type") or "RAW_VALUE").upper()
        if transform not in SUPPORTED_TRANSFORMS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported transform: {transform}")
        self.db.execute(
            text(
                """
                INSERT INTO market_signal_conditions
                (signal_definition_id, condition_group, condition_role, item_type, item_code, transform_type,
                 window_size, comparison_operator, threshold_type, threshold_value, threshold_secondary, weight, is_required, sort_order)
                VALUES (:signal_definition_id, :condition_group, :condition_role, :item_type, :item_code, :transform_type,
                        :window_size, :comparison_operator, :threshold_type, :threshold_value, :threshold_secondary, :weight, :is_required, :sort_order)
                """
            ),
            {
                "signal_definition_id": signal_id,
                "condition_group": condition.get("condition_group") or "A",
                "condition_role": str(condition.get("condition_role") or "REQUIRED").upper(),
                "item_type": str(condition.get("item_type") or "INDICATOR").upper(),
                "item_code": str(condition.get("item_code") or "").upper(),
                "transform_type": transform,
                "window_size": int(condition.get("window_size") or 20),
                "comparison_operator": condition.get("comparison_operator") or ">",
                "threshold_type": str(condition.get("threshold_type") or "ABSOLUTE").upper(),
                "threshold_value": condition.get("threshold_value"),
                "threshold_secondary": condition.get("threshold_secondary"),
                "weight": float(condition.get("weight") or 10),
                "is_required": 1 if condition.get("is_required") else 0,
                "sort_order": int(condition.get("sort_order") or order),
            },
        )

    def _definition_row(self, signal_id: int) -> Any:
        row = self.db.execute(text("SELECT * FROM market_signal_definitions WHERE id = :id"), {"id": signal_id}).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market signal not found")
        return row

    def _condition_rows(self, signal_id: int) -> list[Any]:
        return list(
            self.db.execute(
                text("SELECT * FROM market_signal_conditions WHERE signal_definition_id = :id ORDER BY sort_order, id"),
                {"id": signal_id},
            ).mappings().all()
        )

    def _target_signals(self, *, signal_ids: list[int] | None, active_only: bool) -> list[Any]:
        if signal_ids:
            placeholders = ", ".join(f":id_{idx}" for idx, _ in enumerate(signal_ids))
            params = {f"id_{idx}": signal_id for idx, signal_id in enumerate(signal_ids)}
            return list(
                self.db.execute(
                    text(f"SELECT * FROM market_signal_definitions WHERE id IN ({placeholders})"),
                    params,
                ).mappings().all()
            )
        where = "WHERE status = 'ACTIVE'" if active_only else ""
        return list(self.db.execute(text(f"SELECT * FROM market_signal_definitions {where} ORDER BY id")).mappings().all())

    def _previous_evaluation(self, signal_id: int, observation_date: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT * FROM market_signal_evaluations
                WHERE signal_definition_id = :id AND observation_date < :observation_date
                ORDER BY observation_date DESC
                LIMIT 1
                """
            ),
            {"id": signal_id, "observation_date": observation_date},
        ).mappings().first()
        return dict(row) if row else None

    def _latest_observation_date(self) -> str:
        latest = self.db.execute(
            text(
                """
                SELECT MAX(value_date) FROM market_indicator_values
                UNION ALL
                SELECT MAX(price_date) FROM market_index_daily_prices
                """
            )
        ).scalars().all()
        return max([item for item in latest if item] or [date.today().isoformat()])

    def _simulation_dates(self, signal_id: int, *, years: int) -> list[str]:
        rows = self.db.execute(
            text(
                """
                SELECT DISTINCT v.value_date
                FROM market_signal_conditions c
                JOIN market_indicator_values v ON v.indicator_code = c.item_code
                WHERE c.signal_definition_id = :id AND v.value_date >= date('now', :years)
                ORDER BY v.value_date
                """
            ),
            {"id": signal_id, "years": f"-{max(years, 1)} years"},
        ).scalars().all()
        return [str(row) for row in rows]

    def _snapshot_version(self, signal_id: int, reason: str) -> None:
        signal = dict(self._definition_row(signal_id))
        conditions = [dict(row) for row in self._condition_rows(signal_id)]
        version = int(signal.get("current_version") or 1)
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO market_signal_versions
                (signal_definition_id, version_no, snapshot_json, change_reason)
                VALUES (:signal_definition_id, :version_no, :snapshot_json, :change_reason)
                """
            ),
            {
                "signal_definition_id": signal_id,
                "version_no": version,
                "snapshot_json": json.dumps({"definition": signal, "conditions": conditions}, ensure_ascii=False, sort_keys=True),
                "change_reason": reason,
            },
        )
        self.db.commit()

    def _definition_item(self, row: Any, *, include_conditions: bool) -> dict[str, Any]:
        item = dict(row)
        if include_conditions:
            item["conditions"] = [self._condition_item(condition) for condition in self._condition_rows(int(item["id"]))]
        else:
            item["conditions"] = []
        return item

    @staticmethod
    def _condition_item(row: Any) -> dict[str, Any]:
        item = dict(row)
        item["is_required"] = bool(item.get("is_required"))
        return item

    @staticmethod
    def _evaluation_item(row: Any) -> dict[str, Any]:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "[]")
        item["opposing_evidence"] = json.loads(item.pop("opposing_evidence_json") or "[]")
        item["missing_data"] = json.loads(item.pop("missing_data_json") or "[]")
        return item

    def _indicator_catalog(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT i.indicator_code AS code, i.indicator_name AS name, i.category, i.data_frequency AS frequency,
                       i.unit_label, i.latest_value, i.latest_value_date,
                       m.provider, m.provider_symbol, m.is_enabled, m.is_verified,
                       COALESCE(v.data_count, 0) AS data_count,
                       v.first_value_date, v.latest_value_date AS data_latest_date,
                       COALESCE(u.used_count, 0) AS currently_used_signal_count
                FROM market_indicators i
                LEFT JOIN market_indicator_provider_mappings m
                  ON m.indicator_code = i.indicator_code AND m.is_enabled = 1
                LEFT JOIN (
                    SELECT indicator_code, COUNT(*) AS data_count, MIN(value_date) AS first_value_date, MAX(value_date) AS latest_value_date
                    FROM market_indicator_values
                    WHERE COALESCE(value, close_value) IS NOT NULL
                    GROUP BY indicator_code
                ) v ON v.indicator_code = i.indicator_code
                LEFT JOIN (
                    SELECT item_code, COUNT(DISTINCT signal_definition_id) AS used_count
                    FROM market_signal_conditions
                    WHERE item_type = 'INDICATOR'
                    GROUP BY item_code
                ) u ON u.item_code = i.indicator_code
                WHERE i.is_active = 1
                ORDER BY i.category, i.indicator_code
                """
            )
        ).mappings().all()
        return [self._catalog_item(dict(row)) for row in rows]

    def _gpt_prompt(self, goal_text: str, catalog: list[dict[str, Any]]) -> str:
        catalog_text = "\n".join(
            f"- INDICATOR {item['code']}: {item['name']} / {item['category']} / {item['frequency']} / {item['provider'] or '-'} / "
            f"readiness {item['readiness']} / classification {item['classification']} / rows {item['data_count']} / "
            f"recommended_min {item['recommended_minimum_count']} / insufficient {item['insufficient_count']} / "
            f"simulation_years {item['available_simulation_years'] or 0} / used_signals {item['currently_used_signal_count']} / "
            f"{item['first_value_date'] or '-'}..{item['latest_value_date'] or '-'} / transforms {','.join(item['supported_transforms']) or '-'}"
            for item in catalog[:80]
        )
        transforms = ", ".join(sorted(SUPPORTED_TRANSFORMS))
        return (
            "DrCT market signal rule draft assistant.\n"
            "Use only the listed item codes and transform enums. Do not present buy/sell advice or probabilities.\n"
            "Return JSON with signal_name, economic_meaning, phenomenon, process, expected_result, horizon, "
            "required_conditions, confirm_conditions, opposing_conditions, persistence, release_conditions, cooldown, "
            "missing_indicators, failure_cases, rationale.\n\n"
            f"User goal:\n{goal_text}\n\nSupported transforms:\n{transforms}\n\nIndicator catalog:\n{catalog_text}\n"
        )

    def _validate_gpt_candidate(self, candidate: dict[str, Any], catalog: list[dict[str, Any]]) -> list[str]:
        messages: list[str] = []
        codes = {item["code"] for item in catalog}
        for key in ("signal_name", "phenomenon", "process", "expected_result", "horizon"):
            if not candidate.get(key):
                messages.append(f"missing required field: {key}")
        for bucket in ("required_conditions", "confirm_conditions", "opposing_conditions"):
            for idx, condition in enumerate(candidate.get(bucket) or [], start=1):
                item_code = str(condition.get("item_code") or "").upper()
                transform = str(condition.get("transform_type") or "").upper()
                if item_code not in codes:
                    messages.append(f"{bucket}[{idx}] unknown item_code: {item_code}")
                if transform not in SUPPORTED_TRANSFORMS:
                    messages.append(f"{bucket}[{idx}] unsupported transform_type: {transform}")
                catalog_item = next((item for item in catalog if item["code"] == item_code), None)
                if catalog_item:
                    if catalog_item["classification"] != "AVAILABLE":
                        messages.append(f"{bucket}[{idx}] item_code is not signal-ready: {item_code} ({catalog_item['classification']})")
                    if transform and transform not in set(catalog_item.get("supported_transforms") or []):
                        messages.append(f"{bucket}[{idx}] transform needs more data: {item_code} {transform}")
        return messages

    def _catalog_item(self, row: dict[str, Any]) -> dict[str, Any]:
        data_count = int(row.get("data_count") or 0)
        mapping_ready = bool(int(row.get("is_enabled") or 0)) and bool(int(row.get("is_verified") or 0))
        signal_min = self._signal_minimum_rows(str(row.get("frequency") or "DAILY"), str(row.get("code") or ""))
        supported = self._supported_transforms_for_rows(data_count)
        if data_count >= signal_min:
            readiness = "SIGNAL_READY"
            classification = "AVAILABLE"
            reason = None
        elif data_count > 0:
            readiness = "COMPARE_READY"
            classification = "DATA_INSUFFICIENT"
            reason = f"need at least {signal_min} rows for signal transforms"
        elif mapping_ready:
            readiness = "MAPPING_READY"
            classification = "COLLECTION_REQUIRED"
            reason = "mapping is active but no values are stored"
        else:
            readiness = "MASTER_ONLY"
            classification = "MAPPING_REQUIRED"
            reason = "active mapping is required"
        if str(row.get("provider") or "").upper() == "DERIVED" and data_count == 0:
            classification = "DERIVABLE"
        return {
            "code": row.get("code"),
            "name": row.get("name"),
            "category": row.get("category"),
            "frequency": row.get("frequency"),
            "provider": row.get("provider"),
            "provider_symbol": row.get("provider_symbol"),
            "data_count": data_count,
            "first_value_date": row.get("first_value_date"),
            "latest_value_date": row.get("data_latest_date") or row.get("latest_value_date"),
            "latest_value": row.get("latest_value"),
            "readiness": readiness,
            "classification": classification,
            "recommended_minimum_count": signal_min,
            "insufficient_count": max(signal_min - data_count, 0),
            "available_simulation_years": self._available_years(row.get("first_value_date"), row.get("data_latest_date") or row.get("latest_value_date")),
            "currently_used_signal_count": int(row.get("currently_used_signal_count") or 0),
            "supported_transforms": supported,
            "readiness_reason": reason,
        }

    @staticmethod
    def _signal_minimum_rows(frequency: str, indicator_code: str | None = None) -> int:
        code = str(indicator_code or "").upper()
        if code in {"KR_REAL_POLICY_RATE", "US_REAL_POLICY_RATE"}:
            return 60
        if code == "USD_KRW_VOLATILITY":
            return 252
        normalized = frequency.upper()
        if normalized == "MONTHLY":
            return 24
        if normalized == "WEEKLY":
            return 26
        return 60

    @staticmethod
    def _available_years(first_date: Any, latest_date: Any) -> float | None:
        if not first_date or not latest_date:
            return None
        try:
            first = date.fromisoformat(str(first_date)[:10])
            latest = date.fromisoformat(str(latest_date)[:10])
        except ValueError:
            return None
        return round(max((latest - first).days, 0) / 365.25, 2)

    @staticmethod
    def _supported_transforms_for_rows(data_count: int) -> list[str]:
        transforms = ["RAW_VALUE"] if data_count >= 1 else []
        if data_count >= 2:
            transforms.extend(["CHANGE", "CHANGE_RATE", "MOM"])
        if data_count >= 20:
            transforms.extend(["MOVING_AVERAGE", "SLOPE", "TURN_UP", "TURN_DOWN", "DISTANCE_FROM_MA", "CONSECUTIVE_UP", "CONSECUTIVE_DOWN", "PERSISTENCE"])
        if data_count >= 60:
            transforms.extend(["Z_SCORE", "PERCENTILE", "N_PERIOD_HIGH", "N_PERIOD_LOW", "YOY"])
        if data_count >= 60:
            transforms.extend(["TREND_STATE", "REGRESSION_SLOPE", "NORMALIZED_SLOPE", "TREND_STRENGTH", "TREND_DURATION", "CHANNEL_POSITION"])
        if data_count >= 120:
            transforms.extend(["TREND_BREAK_UP", "TREND_BREAK_DOWN", "BREAK_CONFIRMED_UP", "BREAK_CONFIRMED_DOWN", "FALSE_BREAK_UP", "FALSE_BREAK_DOWN", "REVERSAL_CONFIRMED_UP", "REVERSAL_CONFIRMED_DOWN", "TREND_RESUMED_UP", "TREND_RESUMED_DOWN"])
        return transforms

    @staticmethod
    def _persistence_runs(samples: list[dict[str, Any]]) -> list[int]:
        runs: list[int] = []
        current = 0
        active_states = {"ACTIVE", "STRENGTHENING", "WEAKENING"}
        for sample in samples:
            if sample.get("state") in active_states:
                current += 1
            elif current:
                runs.append(current)
                current = 0
        if current:
            runs.append(current)
        return runs

    def _duplicate_condition_keys(self, signal_id: int) -> list[str]:
        keys: list[str] = []
        seen: set[str] = set()
        for condition in self._condition_rows(signal_id):
            key = "|".join(str(condition.get(part) or "") for part in ("condition_role", "item_type", "item_code", "transform_type", "window_size", "comparison_operator", "threshold_type", "threshold_value"))
            if key in seen:
                keys.append(str(condition.get("item_code") or key))
            seen.add(key)
        return keys

    def _condition_contributions(self, samples: list[dict[str, Any]], conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        active_states = {"ACTIVE", "STRENGTHENING", "WEAKENING"}
        summaries: list[dict[str, Any]] = []
        for condition in conditions:
            condition_id = condition.get("id")
            passed = 0
            active_passed = 0
            contribution_scores: list[float] = []
            for sample in samples:
                evidence_rows = [*sample.get("evidence", []), *sample.get("opposing_evidence", [])]
                matched = [row for row in evidence_rows if row.get("condition_id") == condition_id]
                if not matched:
                    continue
                passed += 1
                if sample.get("state") in active_states:
                    active_passed += 1
                contribution_scores.extend([float(row.get("weight") or 0) for row in matched])
            pass_ratio = passed / len(samples) if samples else 0
            summaries.append(
                {
                    "condition_id": condition_id,
                    "item_code": condition.get("item_code"),
                    "role": condition.get("condition_role"),
                    "transform_type": condition.get("transform_type"),
                    "pass_count": passed,
                    "pass_ratio": round(pass_ratio, 4),
                    "active_pass_ratio": round(active_passed / passed, 4) if passed else 0,
                    "average_contribution": round(sum(contribution_scores) / len(contribution_scores), 2) if contribution_scores else 0,
                    "warning": "ALWAYS_PASS" if pass_ratio > 0.9 else "RARELY_PASS" if samples and pass_ratio < 0.05 else None,
                }
            )
        return summaries

    def _variant_summaries(self, signal: dict[str, Any], conditions: list[dict[str, Any]], dates: list[str]) -> list[dict[str, Any]]:
        variants = [
            ("CURRENT", "현재 룰", conditions),
            ("SENSITIVE", "민감형", [self._adjust_condition_threshold(condition, 0.9) for condition in conditions]),
            ("BALANCED", "균형형", [self._adjust_condition_threshold(condition, 1.0) for condition in conditions]),
            ("CONSERVATIVE", "보수형", [self._adjust_condition_threshold(condition, 1.1) for condition in conditions]),
        ]
        return [self._summarize_variant(key, label, [self._evaluate_signal(signal, observation_date=obs_date, save=False, conditions_override=variant_conditions) for obs_date in dates]) for key, label, variant_conditions in variants]

    def _summarize_variant(self, key: str, label: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
        active_states = {"ACTIVE", "STRENGTHENING", "WEAKENING"}
        active = [sample for sample in samples if sample.get("state") in active_states]
        watch = [sample for sample in samples if sample.get("state") == "WATCH"]
        scores = [float(sample.get("score") or 0) for sample in samples if sample.get("state") != "DATA_INSUFFICIENT"]
        runs = self._persistence_runs(samples)
        return {
            "variant": key,
            "label": label,
            "sample_count": len(samples),
            "active_count": len(active),
            "watch_count": len(watch),
            "triggered_count": len(active),
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
            "average_persistence": round(sum(runs) / len(runs), 2) if runs else None,
            "max_persistence": max(runs) if runs else 0,
            "data_insufficient_count": sum(1 for sample in samples if sample.get("state") == "DATA_INSUFFICIENT"),
            "recent_state": samples[-1].get("state") if samples else None,
        }

    @staticmethod
    def _adjust_condition_threshold(condition: dict[str, Any], multiplier: float) -> dict[str, Any]:
        adjusted = dict(condition)
        threshold = adjusted.get("threshold_value")
        if threshold is None:
            return adjusted
        operator = str(adjusted.get("comparison_operator") or ">")
        value = float(threshold)
        if operator in {"<", "<="}:
            adjusted["threshold_value"] = value / multiplier if multiplier else value
        else:
            adjusted["threshold_value"] = value * multiplier
        return adjusted

    @staticmethod
    def _transition_points(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        previous_state: str | None = None
        for sample in samples:
            state = str(sample.get("state") or "")
            if previous_state and state != previous_state:
                points.append(
                    {
                        "observation_date": sample.get("observation_date"),
                        "previous_state": previous_state,
                        "state": state,
                        "score": sample.get("score"),
                    }
                )
            previous_state = state
        return points[-80:]

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    @staticmethod
    def _consecutive(values: list[float], *, upward: bool) -> int:
        count = 0
        for idx in range(len(values) - 1, 0, -1):
            if upward and values[idx] > values[idx - 1]:
                count += 1
            elif not upward and values[idx] < values[idx - 1]:
                count += 1
            else:
                break
        return count
