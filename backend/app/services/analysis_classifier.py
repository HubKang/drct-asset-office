from __future__ import annotations

from collections.abc import Iterable

from backend.app.entities.classification_rule import ClassificationRule


class AnalysisClassifier:
    _DISCLOSURE_EVENT_DEFAULT_RISK: dict[str, str] = {
        "소송": "high",
        "자본": "medium",
        "투자": "medium",
        "지분변동": "medium",
        "계약": "low",
        "실적": "low",
        "배당": "low",
        "자사주": "low",
        "주주총회": "low",
        "기타": "unknown",
    }

    def _keywords(self, raw: str) -> list[str]:
        return [token.strip().lower() for token in raw.split(",") if token.strip()]

    def _matched(self, text: str, raw_keywords: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in self._keywords(raw_keywords))

    def _clamp_score(self, score: int) -> int:
        return max(0, min(score, 100))

    def _default_risk_level_for_event(self, event_type: str) -> str:
        return self._DISCLOSURE_EVENT_DEFAULT_RISK.get(event_type, "unknown")

    def classify_news(
        self,
        title: str | None,
        summary: str | None,
        ai_summary: str | None,
        rules: Iterable[ClassificationRule],
    ) -> dict[str, str | int]:
        text = " ".join([title or "", summary or "", ai_summary or ""]).strip()
        tags: list[str] = []
        score = 50
        sentiment_candidates: list[tuple[int, str]] = []

        for rule in rules:
            if rule.target_type != "news" or rule.is_active != 1:
                continue
            if not self._matched(text, rule.keywords):
                continue

            score += int(rule.score_delta or 0)
            if rule.output_field == "ai_tags":
                if rule.output_value and rule.output_value not in tags:
                    tags.append(rule.output_value)
            elif rule.output_field == "ai_sentiment":
                sentiment_candidates.append((int(rule.priority or 100), rule.output_value))
            elif rule.output_field == "ai_importance_score":
                try:
                    score = int(rule.output_value)
                except ValueError:
                    pass

        sentiment = "neutral"
        if sentiment_candidates:
            sentiment_candidates.sort(key=lambda x: x[0])
            top_priority = sentiment_candidates[0][0]
            top_values = [value for priority, value in sentiment_candidates if priority == top_priority]
            if "positive" in top_values and "negative" in top_values:
                sentiment = "neutral"
            elif "negative" in top_values:
                sentiment = "negative"
            elif "positive" in top_values:
                sentiment = "positive"
            else:
                sentiment = top_values[0]

        if not tags:
            tags.append("뉴스")

        return {
            "ai_tags": ",".join(tags),
            "ai_sentiment": sentiment,
            "ai_importance_score": self._clamp_score(score),
        }

    def classify_disclosure(
        self,
        disclosure_title: str | None,
        disclosure_type: str | None,
        ai_summary: str | None,
        rules: Iterable[ClassificationRule],
    ) -> dict[str, str | int]:
        text = " ".join([disclosure_title or "", disclosure_type or "", ai_summary or ""]).strip()
        tags: list[str] = ["공시"]
        event_candidates: list[tuple[int, str]] = []
        risk_candidates: list[tuple[int, str]] = []
        score = 50

        for rule in rules:
            if rule.target_type != "disclosure" or rule.is_active != 1:
                continue
            if not self._matched(text, rule.keywords):
                continue

            score += int(rule.score_delta or 0)
            if rule.output_field == "ai_tags":
                if rule.output_value and rule.output_value not in tags:
                    tags.append(rule.output_value)
            elif rule.output_field == "ai_event_type":
                event_candidates.append((int(rule.priority or 100), rule.output_value))
            elif rule.output_field == "ai_risk_level":
                risk_candidates.append((int(rule.priority or 100), rule.output_value))
            elif rule.output_field == "ai_importance_score":
                try:
                    score = int(rule.output_value)
                except ValueError:
                    pass

        event_type = "기타"
        if event_candidates:
            event_candidates.sort(key=lambda x: x[0])
            event_type = event_candidates[0][1]
            if event_type not in tags:
                tags.append(event_type)

        risk_level = "unknown"
        if risk_candidates:
            risk_candidates.sort(key=lambda x: x[0])
            risk_level = risk_candidates[0][1]
        elif event_type:
            risk_level = self._default_risk_level_for_event(event_type)

        if risk_level in {"medium", "high"} and "리스크" not in tags:
            tags.append("리스크")

        return {
            "ai_tags": ",".join(tags),
            "ai_event_type": event_type,
            "ai_risk_level": risk_level,
            "ai_importance_score": self._clamp_score(score),
        }
