from __future__ import annotations

from collections.abc import Iterable

from backend.app.entities.classification_rule import ClassificationRule


class AnalysisClassifier:
    _NEWS_EVENT_KEYWORDS: dict[str, list[str]] = {
        "실적": ["실적", "영업이익", "매출", "흑자", "적자", "어닝", "잠정실적"],
        "계약": ["계약", "공급계약", "체결", "해지"],
        "수주": ["수주", "발주", "납품"],
        "투자": ["투자", "증설", "공장", "설비"],
        "인수합병": ["인수", "합병", "m&a", "지분 인수"],
        "신제품": ["신제품", "출시", "런칭"],
        "임상": ["임상", "fda", "승인"],
        "규제": ["규제", "제재", "리콜"],
        "소송": ["소송", "분쟁", "판결"],
        "자금조달": ["유상증자", "전환사채", "cb", "bw", "자금조달"],
        "지분변동": ["지분", "최대주주", "보유비율"],
        "경영변동": ["대표이사", "임원", "경영진", "사임", "선임"],
    }
    _NEWS_POSITIVE_KEYWORDS = {
        "수주",
        "계약 체결",
        "실적 개선",
        "흑자",
        "증가",
        "증설",
        "신제품",
        "승인",
        "배당 확대",
        "자사주 취득",
    }
    _NEWS_NEGATIVE_KEYWORDS = {
        "적자",
        "부진",
        "손실",
        "계약 해지",
        "소송",
        "횡령",
        "배임",
        "감사의견",
        "상장폐지",
        "유상증자",
        "전환사채",
        "규제",
        "리콜",
        "급락",
    }

    _DISCLOSURE_EVENT_KEYWORDS: dict[str, list[str]] = {
        "실적": ["실적", "잠정", "영업실적", "손익구조", "매출액"],
        "배당": ["배당", "현금배당", "주당배당금", "중간배당", "결산배당"],
        "자사주": ["자기주식", "자사주", "자기주식취득", "자기주식처분"],
        "계약": ["계약", "공급계약", "단일판매"],
        "수주": ["수주", "발주", "수주계약"],
        "소송": ["소송", "분쟁", "판결", "중재"],
        "유상증자": ["유상증자"],
        "전환사채": ["전환사채", "cb"],
        "신주인수권부사채": ["신주인수권부사채", "bw"],
        "무상증자": ["무상증자"],
        "감자": ["감자"],
        "지분변동": ["지분변동", "대량보유", "소유주식변동"],
        "임원변동": ["임원", "대표이사", "사내이사", "사외이사"],
        "최대주주변경": ["최대주주 변경", "최대주주"],
        "주주총회": ["주주총회", "의결권"],
        "투자": ["신규시설투자", "투자판단", "출자"],
        "합병": ["합병"],
        "분할": ["분할"],
        "영업정지": ["영업정지"],
        "감사의견": ["감사의견", "한정", "부적정", "의견거절"],
    }

    _DISCLOSURE_EVENT_DEFAULT_RISK: dict[str, str] = {
        "소송": "high",
        "영업정지": "high",
        "감사의견": "high",
        "유상증자": "medium",
        "전환사채": "medium",
        "신주인수권부사채": "medium",
        "감자": "medium",
        "최대주주변경": "medium",
        "지분변동": "medium",
        "투자": "medium",
        "합병": "medium",
        "분할": "medium",
        "계약": "low",
        "수주": "low",
        "실적": "low",
        "배당": "low",
        "자사주": "low",
        "주주총회": "low",
        "임원변동": "low",
        "기타": "unknown",
    }

    def _keywords(self, raw: str) -> list[str]:
        return [token.strip().lower() for token in raw.split(",") if token.strip()]

    def _matched(self, text: str, raw_keywords: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in self._keywords(raw_keywords))

    @staticmethod
    def _clamp_score(score: int) -> int:
        return max(0, min(score, 100))

    def _dedupe_rules(self, rules: Iterable[ClassificationRule], target_type: str) -> list[ClassificationRule]:
        unique: dict[tuple[str, str, str, str], ClassificationRule] = {}
        for rule in rules:
            if rule.target_type != target_type or rule.is_active != 1:
                continue
            key = (
                rule.keywords.strip().lower(),
                rule.output_field.strip().lower(),
                rule.output_value.strip().lower(),
                rule.rule_group.strip().lower(),
            )
            prev = unique.get(key)
            if prev is None or int(rule.priority or 100) < int(prev.priority or 100):
                unique[key] = rule
        return list(unique.values())

    @staticmethod
    def _extract_event_type(text: str, mapping: dict[str, list[str]]) -> str:
        lowered = text.lower()
        for event_type, keywords in mapping.items():
            if any(keyword.lower() in lowered for keyword in keywords):
                return event_type
        return "기타"

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
        deduped_rules = self._dedupe_rules(rules, "news")
        tags: list[str] = []
        score = 50
        sentiment_candidates: list[tuple[int, str]] = []

        for rule in deduped_rules:
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

        lowered = text.lower()
        event_type = self._extract_event_type(text, self._NEWS_EVENT_KEYWORDS)
        if event_type != "기타" and event_type not in tags:
            tags.append(event_type)

        if sentiment == "neutral":
            has_pos = any(keyword in lowered for keyword in self._NEWS_POSITIVE_KEYWORDS)
            has_neg = any(keyword in lowered for keyword in self._NEWS_NEGATIVE_KEYWORDS)
            if has_pos and not has_neg:
                sentiment = "positive"
            elif has_neg and not has_pos:
                sentiment = "negative"

        if sentiment == "positive":
            score += 8
        elif sentiment == "negative":
            score -= 10

        if event_type in {"실적", "계약", "수주", "투자", "인수합병", "신제품", "임상"}:
            score += 8
        elif event_type in {"소송", "규제", "자금조달"}:
            score -= 6

        if not tags:
            tags = [event_type if event_type != "기타" else "뉴스"]

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
        deduped_rules = self._dedupe_rules(rules, "disclosure")
        tags: list[str] = ["공시"]
        event_candidates: list[tuple[int, str]] = []
        risk_candidates: list[tuple[int, str]] = []
        score = 50

        for rule in deduped_rules:
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

        heuristic_event = self._extract_event_type(text, self._DISCLOSURE_EVENT_KEYWORDS)
        event_type = heuristic_event
        if event_candidates:
            event_candidates.sort(key=lambda x: x[0])
            event_type = event_candidates[0][1]
        if not event_type:
            event_type = "기타"
        if event_type not in tags:
            tags.append(event_type)

        risk_level = "unknown"
        if risk_candidates:
            risk_candidates.sort(key=lambda x: x[0])
            risk_level = risk_candidates[0][1]
        if risk_level in {"unknown", "", None}:
            risk_level = self._default_risk_level_for_event(event_type)

        if risk_level == "high":
            score = min(score, 45)
        elif risk_level == "medium":
            score = min(score, 65)
        elif risk_level == "low":
            score = max(score, 55)

        if risk_level in {"medium", "high"} and "리스크" not in tags:
            tags.append("리스크")

        return {
            "ai_tags": ",".join(tags),
            "ai_event_type": event_type,
            "ai_risk_level": risk_level,
            "ai_importance_score": self._clamp_score(score),
        }
