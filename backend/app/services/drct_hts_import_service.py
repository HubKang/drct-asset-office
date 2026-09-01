from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

from backend.app.services.drct_rule_engine import BooleanExpression, ExpressionError


STATUS_LABELS = {
    "AUTO_CONVERTED": "자동 변환 완료",
    "NEEDS_CONFIRMATION": "사용자 확인 필요",
    "UNSUPPORTED": "현재 자동 변환 미지원",
    "INVALID_SOURCE": "원본 형식 확인 필요",
}
FIELD_CODES = {"시가": "OPEN", "고가": "HIGH", "저가": "LOW", "종가": "CLOSE"}
FIELD_LABELS = {value: key for key, value in FIELD_CODES.items()}
OPERATORS = {">": "GT", ">=": "GTE", "<": "LT", "<=": "LTE", "이상": "GTE", "이하": "LTE", "초과": "GT", "미만": "LT"}


class DrctHtsImportService:
    """Deterministic HTS reference parser. Results are transient and never persisted here."""

    def __init__(self) -> None:
        self.templates: list[Callable[[str, str, dict[str, Any]], dict[str, Any] | None]] = [
            self._market_cap, self._price_range, self._ma_array, self._ma_trend,
            self._period_value, self._period_change, self._price_chain, self._pct_change,
            self._detailed_ma, self._ma_cross, self._price_ma, self._ma_compare, self._distance,
        ]

    @staticmethod
    def normalize(value: str) -> str:
        value = unicodedata.normalize("NFKC", value or "").replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    @staticmethod
    def _normalize_expression(value: str) -> str:
        value = unicodedata.normalize("NFKC", value or "")
        value = re.sub(r"\bAND\b|그리고", "AND", value, flags=re.IGNORECASE)
        value = re.sub(r"\bOR\b|또는", "OR", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _split(self, text: str, explicit_expression: str | None) -> tuple[list[tuple[str, str, str]], str]:
        normalized = self.normalize(text)
        expression = self._normalize_expression(explicit_expression or "")
        if not expression:
            match = re.search(r"(?:최종\s*)?조건식\s*[:：]\s*(.+)$", normalized, re.IGNORECASE | re.DOTALL)
            if match:
                expression = self._normalize_expression(match.group(1).splitlines()[0])
                normalized = normalized[:match.start()].strip()
        headers = list(re.finditer(r"(?m)^\s*([A-Z])\s+([^:\n]+)\s*[:：]\s*", normalized))
        conditions: list[tuple[str, str, str]] = []
        for index, match in enumerate(headers):
            end = headers[index + 1].start() if index + 1 < len(headers) else len(normalized)
            body = re.sub(r"\s+", " ", normalized[match.end():end]).strip()
            source = f"{match.group(1)} {match.group(2).strip()}: {body}".strip()
            conditions.append((match.group(1), match.group(2).strip(), source))
        return conditions, expression

    def parse(self, text: str, expression: str | None, resolutions: dict[str, dict[str, str | int | float]]) -> dict[str, Any]:
        sources, normalized_expression = self._split(text, expression)
        expression_error: str | None = None
        try:
            referenced = {token for token in BooleanExpression.to_rpn(normalized_expression) if token not in {"AND", "OR"}}
        except ExpressionError as exc:
            referenced = set()
            expression_error = str(exc)

        results: list[dict[str, Any]] = []
        groups: list[dict[str, Any]] = []
        seen: set[str] = set()
        for code, title, source in sources:
            seen.add(code)
            resolution = dict(resolutions.get(code, {}))
            parsed = next((item for parser in self.templates if (item := parser(title, source, resolution)) is not None), None)
            if parsed is None:
                parsed = self._result("UNSUPPORTED", "원문을 보존했지만 현재 지원하는 변환 유형이 아닙니다.", issue="지원 유형을 확인해 주세요.")
            required = code in referenced
            parsed.update({
                "code": code, "title": title, "source_text": source, "required": required,
                "used_label": "사용 조건" if required else "미사용 조건",
                "status_label": STATUS_LABELS[parsed["status"]],
            })
            group = parsed.pop("group", None)
            results.append(parsed)
            if required and parsed["status"] == "AUTO_CONVERTED" and group:
                groups.append({"code": code, "source_text": source, **group})

        missing_codes = sorted(referenced - seen)
        for code in missing_codes:
            results.append({
                "code": code, "title": "원본 조건 없음", "source_text": "", "status": "INVALID_SOURCE",
                "status_label": STATUS_LABELS["INVALID_SOURCE"], "required": True, "used_label": "사용 조건",
                "human_description": "조건 조합에서 참조하지만 원본 조건이 없습니다.", "issue": "원본에 해당 조건을 추가해 주세요.",
                "resolution_kind": None, "resolution_options": [],
            })

        blocking = [item for item in results if item["required"] and item["status"] != "AUTO_CONVERTED"]
        if expression_error or not sources or missing_codes:
            overall = "INVALID"
        elif blocking:
            overall = "NEEDS_REVIEW"
        else:
            overall = "READY"
        counts = {status: sum(item["status"] == status for item in results) for status in STATUS_LABELS}
        rule = {"schema_version": 2, "conditions": groups, "expression": normalized_expression} if overall == "READY" else None
        return {
            "status": overall,
            "status_label": {"READY": "저장 준비 완료", "NEEDS_REVIEW": "사용자 검토 필요", "INVALID": "원본 확인 필요"}[overall],
            "normalized_expression": normalized_expression,
            "expression_korean": normalized_expression.replace("AND", "그리고").replace("OR", "또는"),
            "conditions": results,
            "summary": {"total": len(results), "auto_converted": counts["AUTO_CONVERTED"],
                        "needs_confirmation": counts["NEEDS_CONFIRMATION"], "unsupported": counts["UNSUPPORTED"],
                        "invalid_source": counts["INVALID_SOURCE"]},
            "rule": rule,
        }

    @staticmethod
    def _result(status: str, description: str, *, predicates: list[dict[str, Any]] | None = None,
                label: str | None = None, join: str = "AND", issue: str | None = None,
                resolution_kind: str | None = None, options: list[dict[str, str]] | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": status, "human_description": description, "issue": issue,
            "resolution_kind": resolution_kind, "resolution_options": options or [],
        }
        if predicates:
            result["group"] = {"label": label or description, "join": join, "configured": True, "predicates": predicates}
        return result

    @staticmethod
    def _predicate(kind: str, label: str, **params: Any) -> dict[str, Any]:
        return {"type": kind, "label": label, "configured": True, "params": params}

    @staticmethod
    def _operand(field: str, offset: int) -> dict[str, Any]:
        return {"kind": "PRICE", "field": field, "offset": offset}

    @staticmethod
    def _ma_operand(period: int, offset: int) -> dict[str, Any]:
        return {"kind": "MA", "period": period, "offset": offset}

    def _market_cap(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "시가총액" not in title:
            return None
        match = re.search(r"([\d,.]+)\s*(십억원|억원|원)\s*(이상|이하|초과|미만)", source)
        if not match:
            return self._result("NEEDS_CONFIRMATION", "시가총액 기준 금액 또는 비교 관계가 완전하지 않습니다.", issue="금액과 관계를 원본에서 확인해 주세요.")
        scale = {"십억원": 1_000_000_000, "억원": 100_000_000, "원": 1}[match.group(2)]
        value, operator = float(match.group(1).replace(",", "")) * scale, OPERATORS[match.group(3)]
        return self._result("AUTO_CONVERTED", f"시가총액이 {match.group(1)}{match.group(2)} {match.group(3)}", predicates=[self._predicate("MARKET_CAP_COMPARE", "시가총액 기준", operator=operator, value=value)])

    def _price_range(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "주가범위" not in title:
            return None
        head = re.search(r"(\d+)(?:일전|봉전).*?(시가|고가|저가|종가)", source)
        limits = re.findall(r"([\d,.]+)\s*(이상|이하|초과|미만)", source)
        if not head or not limits:
            return self._result("NEEDS_CONFIRMATION", "가격 범위의 기준 시점·가격 종류·범위를 확인해야 합니다.")
        offset, field = int(head.group(1)), FIELD_CODES[head.group(2)]
        predicates = [self._predicate("PRICE_COMPARE_VALUE", f"{offset}봉 전 {head.group(2)} {relation} {value}", price_field=field, offset=offset, operator=OPERATORS[relation], value=float(value.replace(",", ""))) for value, relation in limits]
        return self._result("AUTO_CONVERTED", f"{offset}봉 전 {head.group(2)}가 " + ", ".join(f"{v} {r}" for v, r in limits), predicates=predicates)

    def _ma_array(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "이평배열" not in title:
            return None
        offset_match = re.search(r"(\d+)봉전", source)
        periods = [int(value) for value in re.findall(r"(\d+)이평", source)]
        if not offset_match or len(periods) < 2 or not all(period in {5, 10, 20, 60, 120, 240} for period in periods):
            return self._result("UNSUPPORTED", "이동평균 배열의 기간 또는 순서를 변환할 수 없습니다.")
        offset = int(offset_match.group(1))
        predicates = [self._predicate("MA_COMPARE", f"{left}일선이 {right}일선 위", lhs_period=left, lhs_offset=offset, rhs_period=right, rhs_offset=offset, operator="GT") for left, right in zip(periods, periods[1:])]
        return self._result("AUTO_CONVERTED", " > ".join(f"{period}일 이동평균" for period in periods), predicates=predicates)

    def _ma_trend(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "이평추세" not in title:
            return None
        match = re.search(r"(\d+)봉전.*?종가\s*(\d+)\)?이평\s*(상승|하락)추세유지\s*(\d+)회", source)
        if not match:
            return self._result("NEEDS_CONFIRMATION", "이동평균 기간·방향·유지 횟수를 확인해야 합니다.")
        offset, period, direction, count = int(match.group(1)), int(match.group(2)), match.group(3), int(match.group(4))
        predicate = self._predicate("MA_TREND", f"{period}일선 {direction} 추세 {count}회", ma_period=period, direction="UP" if direction == "상승" else "DOWN", count=count, offset=offset)
        return self._result("AUTO_CONVERTED", f"{period}일 이동평균이 {direction} 추세를 {count}회 유지", predicates=[predicate])

    def _price_chain(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "주가비교" not in title:
            return None
        parts = list(re.finditer(r"(\d+)봉전\s*(시가|고가|저가|종가)?", source))
        if len(parts) < 2:
            return self._result("NEEDS_CONFIRMATION", "비교할 가격 시점이 충분하지 않습니다.")
        selected = str(resolution.get("price_field", ""))
        if any(not match.group(2) for match in parts) and selected not in FIELD_LABELS:
            return self._result("NEEDS_CONFIRMATION", "일부 비교 가격 종류가 원본에서 잘려 있습니다.", issue="잘린 위치의 가격 종류를 선택해 주세요.", resolution_kind="PRICE_FIELD", options=[{"value": key, "label": value} for key, value in FIELD_LABELS.items()])
        predicates = []
        descriptions = []
        for left, right in zip(parts, parts[1:]):
            between = source[left.end():right.start()]
            symbol_match = re.search(r"(<=|>=|<|>)", between)
            if not symbol_match:
                return self._result("NEEDS_CONFIRMATION", "가격 사이의 비교 관계를 확인해야 합니다.", resolution_kind="RELATION", options=self._relation_options())
            left_field = FIELD_CODES.get(left.group(2) or "", selected)
            right_field = FIELD_CODES.get(right.group(2) or "", selected)
            predicates.append(self._predicate("PRICE_COMPARE_PRICE", "가격 흐름 비교", lhs=self._operand(left_field, int(left.group(1))), rhs=self._operand(right_field, int(right.group(1))), operator=OPERATORS[symbol_match.group(1)]))
            descriptions.append(f"{left.group(1)}봉 전 {FIELD_LABELS[left_field]} {symbol_match.group(1)} {right.group(1)}봉 전 {FIELD_LABELS[right_field]}")
        return self._result("AUTO_CONVERTED", ", ".join(descriptions), predicates=predicates)

    def _pct_change(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "주가등락률" not in title:
            return None
        match = re.search(r"(\d+)봉전.*?(시가|고가|저가|종가)대비\s*(\d+)봉전\s*(시가|고가|저가|종가)등락률\s*([\d.]+)%\s*(이상|이하|초과|미만)", source)
        if not match:
            return self._result("NEEDS_CONFIRMATION", "등락률의 두 가격과 임계값을 확인해야 합니다.")
        a_offset, a_field, b_offset, b_field, value, relation = match.groups()
        predicate = self._predicate("PCT_CHANGE", "구간 가격 등락률", lhs=self._operand(FIELD_CODES[a_field], int(a_offset)), rhs=self._operand(FIELD_CODES[b_field], int(b_offset)), operator=OPERATORS[relation], value=float(value))
        return self._result("AUTO_CONVERTED", f"{a_offset}봉 전 {a_field} 대비 {b_offset}봉 전 {b_field} 등락률 {value}% {relation}", predicates=[predicate])

    def _detailed_ma(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "상세이평" not in title:
            return None
        periods = [int(value) for value in re.findall(r"종가\s*(\d+)\)?이평", source)]
        offset_match = re.search(r"(\d+)봉전", source)
        if len(periods) < 2 or not offset_match:
            return self._result("UNSUPPORTED", "상세 이동평균 비교의 두 기준을 읽을 수 없습니다.")
        relation = str(resolution.get("relation", ""))
        if relation not in {"CROSS_UP", "CROSS_DOWN", "GT", "LT"}:
            return self._result("NEEDS_CONFIRMATION", "두 이동평균 사이의 관계가 원본에서 잘려 있습니다.", issue="원래 의도한 관계를 선택해 주세요.", resolution_kind="RELATION", options=self._relation_options())
        offset = int(offset_match.group(1))
        lhs = self._operand("CLOSE", offset) if periods[0] == 1 else self._ma_operand(periods[0], offset)
        rhs = self._operand("CLOSE", offset) if periods[1] == 1 else self._ma_operand(periods[1], offset)
        if relation in {"CROSS_UP", "CROSS_DOWN"}:
            predicate = self._predicate(relation, "가격과 이동평균 교차", lhs=lhs, rhs=rhs)
        elif lhs["kind"] == "PRICE" and rhs["kind"] == "MA":
            predicate = self._predicate("PRICE_MA_COMPARE", "가격과 이동평균 비교", price_field="CLOSE", price_offset=offset, ma_period=periods[1], ma_offset=offset, operator=relation)
        else:
            predicate = self._predicate("MA_COMPARE", "이동평균 비교", lhs_period=periods[0], lhs_offset=offset, rhs_period=periods[1], rhs_offset=offset, operator=relation)
        label = {"CROSS_UP": "상향 돌파", "CROSS_DOWN": "하향 돌파", "GT": "위", "LT": "아래"}[relation]
        return self._result("AUTO_CONVERTED", f"{periods[0]}일 기준이 {periods[1]}일 이동평균을 기준으로 {label}", predicates=[predicate])

    def _ma_cross(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "이평돌파" not in title or "상세" in title:
            return None
        match = re.search(r"(\d+)봉전.*?종가\s*(\d+)\)?이평.*?종가\s*(\d+)\)?이평\s*(골든크로스|데드크로스)", source)
        if not match:
            return self._result("NEEDS_CONFIRMATION", "교차 방향 또는 이동평균 기간을 확인해야 합니다.")
        offset, first, second, direction = int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4)
        lhs = self._operand("CLOSE", offset) if first == 1 else self._ma_operand(first, offset)
        rhs = self._operand("CLOSE", offset) if second == 1 else self._ma_operand(second, offset)
        predicate = self._predicate("CROSS_UP" if direction == "골든크로스" else "CROSS_DOWN", f"{direction}", lhs=lhs, rhs=rhs)
        return self._result("AUTO_CONVERTED", f"{first}일 기준과 {second}일 이동평균의 {direction}", predicates=[predicate])

    def _price_ma(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "가격-이동평균" not in title:
            return None
        match = re.search(r"(\d+)봉전.*?종가\s*(\d+)\)?이평\s*(<|>)\s*(시가|고가|저가|종가)", source)
        if not match:
            return self._result("NEEDS_CONFIRMATION", "가격과 이동평균의 비교 관계를 확인해야 합니다.")
        offset, period, symbol, field_label = int(match.group(1)), int(match.group(2)), match.group(3), match.group(4)
        # Source is MA < PRICE; evaluator is PRICE > MA.
        operator = "GT" if symbol == "<" else "LT"
        predicate = self._predicate("PRICE_MA_COMPARE", "가격과 이동평균 비교", price_field=FIELD_CODES[field_label], price_offset=offset, ma_period=period, ma_offset=offset, operator=operator)
        return self._result("AUTO_CONVERTED", f"{field_label}가 {period}일 이동평균보다 {'위' if operator == 'GT' else '아래'}", predicates=[predicate])

    def _ma_compare(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "이평비교" not in title or "상세" in title:
            return None
        match = re.search(r"(\d+)봉전.*?종가\s*(\d+)\)?이평\s*(<|>)\s*\(?종가\s*(\d+)\)?이평", source)
        if not match:
            return self._result("NEEDS_CONFIRMATION", "두 이동평균의 비교 관계를 확인해야 합니다.")
        offset, left, symbol, right = int(match.group(1)), int(match.group(2)), match.group(3), int(match.group(4))
        predicate = self._predicate("MA_COMPARE", "이동평균 비교", lhs_period=left, lhs_offset=offset, rhs_period=right, rhs_offset=offset, operator=OPERATORS[symbol])
        return self._result("AUTO_CONVERTED", f"{left}일 이동평균 {symbol} {right}일 이동평균", predicates=[predicate])

    def _distance(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "이평이격도" not in title:
            return None
        match = re.search(r"(\d+)봉전.*?종가\s*1\s*,\s*종가\s*(\d+)\).*?([\d.]+)%\s*이내", source)
        if not match:
            return self._result("NEEDS_CONFIRMATION", "이격도 기준 기간과 비율을 확인해야 합니다.")
        offset, period, value = int(match.group(1)), int(match.group(2)), float(match.group(3))
        predicate = self._predicate("DISTANCE_PCT", "가격과 이동평균 이격률", lhs=self._operand("CLOSE", offset), rhs=self._ma_operand(period, offset), operator="LTE", value=value)
        return self._result("AUTO_CONVERTED", f"종가와 {period}일 이동평균의 이격률이 {value:g}% 이내", predicates=[predicate])

    def _period_change(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "기간내 등락률" not in title:
            return None
        match = re.search(r"(\d+)봉전\s*(\d+)봉이내.*?(시가|고가|저가|종가)\s*([\d.]+)%\s*(이상|이하|초과|미만)", source)
        if not match:
            return self._result("NEEDS_CONFIRMATION", "기간 내 가격 변화의 기간·가격·임계값을 확인해야 합니다.")
        offset, lookback, field, value, relation = int(match.group(1)), int(match.group(2)), match.group(3), float(match.group(4)), match.group(5)
        if offset != 0:
            return self._result("UNSUPPORTED", "기준일이 0봉 전이 아닌 기간 내 등락률은 아직 지원하지 않습니다.")
        predicate = self._predicate("PERIOD_EXISTS_PRICE_CHANGE", "기간 내 가격 상승", price_field=FIELD_CODES[field], lookback=lookback, operator=OPERATORS[relation], value=value)
        return self._result("AUTO_CONVERTED", f"최근 {lookback}봉 안에 전일 종가 대비 {field} {value:g}% {relation}", predicates=[predicate])

    def _period_value(self, title: str, source: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
        if "기간내 거래대금" not in title:
            return None
        lookback_match = re.search(r"(\d+)봉전\s*(\d+)봉이내", source)
        threshold_match = re.search(r"([\d,.]+)\s*(십억원|억원|백만원|만원|원)\s*(이상|이하|초과|미만)", source)
        threshold = resolution.get("threshold")
        if not lookback_match:
            return self._result("UNSUPPORTED", "거래대금 검색 기간을 읽을 수 없습니다.")
        if not threshold_match and threshold in (None, ""):
            return self._result("NEEDS_CONFIRMATION", "거래대금 임계값이 원본에서 잘려 있습니다.", issue="원래 금액(원)을 입력해 주세요.", resolution_kind="THRESHOLD")
        if threshold_match:
            scales = {"십억원": 1_000_000_000, "억원": 100_000_000, "백만원": 1_000_000, "만원": 10_000, "원": 1}
            value = float(threshold_match.group(1).replace(",", "")) * scales[threshold_match.group(2)]
            operator, relation = OPERATORS[threshold_match.group(3)], threshold_match.group(3)
        else:
            try:
                value = float(threshold)
            except (TypeError, ValueError):
                return self._result("NEEDS_CONFIRMATION", "거래대금 임계값은 0보다 큰 숫자여야 합니다.", resolution_kind="THRESHOLD")
            if value <= 0:
                return self._result("NEEDS_CONFIRMATION", "거래대금 임계값은 0보다 큰 숫자여야 합니다.", resolution_kind="THRESHOLD")
            operator, relation = "GTE", "이상"
        lookback = int(lookback_match.group(2))
        predicate = self._predicate("PERIOD_VALUE_COMPARE", "기간 내 거래대금", value_field="TRADING_VALUE", lookback=lookback, operator=operator, value=value)
        return self._result("AUTO_CONVERTED", f"최근 {lookback}봉 안에 거래대금 {value:,.0f}원 {relation}", predicates=[predicate])

    @staticmethod
    def _relation_options() -> list[dict[str, str]]:
        return [
            {"value": "CROSS_UP", "label": "상향 돌파"}, {"value": "CROSS_DOWN", "label": "하향 돌파"},
            {"value": "GT", "label": "위에 있음"}, {"value": "LT", "label": "아래에 있음"},
        ]
