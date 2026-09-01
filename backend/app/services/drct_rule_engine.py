from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable


SUPPORTED_OPERATORS = {"GT", "GTE", "LT", "LTE", "EQ"}
SUPPORTED_PRICE_FIELDS = {"OPEN", "HIGH", "LOW", "CLOSE"}
SUPPORTED_VALUE_FIELDS = {"VOLUME", "TRADING_VALUE"}
SUPPORTED_MA_PERIODS = {5, 10, 20, 60, 120, 240}
SUPPORTED_CONDITION_TYPES = {
    "MARKET_CAP_COMPARE",
    "PRICE_COMPARE_VALUE",
    "PRICE_COMPARE_PRICE",
    "MA_COMPARE",
    "PRICE_MA_COMPARE",
    "MA_TREND",
    "CROSS_UP",
    "CROSS_DOWN",
    "PCT_CHANGE",
    "DISTANCE_PCT",
    "PERIOD_EXISTS_PRICE_CHANGE",
    "PERIOD_VALUE_COMPARE",
}


@dataclass(frozen=True)
class RuleValidationResult:
    status: str
    errors: list[dict[str, str]]
    required_lookback: int


class ExpressionError(ValueError):
    pass


class DataIncompleteError(ValueError):
    pass


class BooleanExpression:
    _token = re.compile(r"\s*(AND|OR|\(|\)|[A-Z][A-Z0-9_]*)\s*", re.IGNORECASE)

    @classmethod
    def tokens(cls, expression: str) -> list[str]:
        result: list[str] = []
        position = 0
        while position < len(expression):
            match = cls._token.match(expression, position)
            if match is None:
                raise ExpressionError(f"지원하지 않는 토큰이 있습니다: {expression[position:position + 12]}")
            result.append(match.group(1).upper())
            position = match.end()
        if not result:
            raise ExpressionError("조건 조합이 비어 있습니다.")
        return result

    @classmethod
    def to_rpn(cls, expression: str) -> list[str]:
        tokens = cls.tokens(expression)
        output: list[str] = []
        stack: list[str] = []
        precedence = {"OR": 1, "AND": 2}
        expects_operand = True
        for token in tokens:
            if token not in {"AND", "OR", "(", ")"}:
                if not expects_operand:
                    raise ExpressionError("조건 코드 사이에 AND 또는 OR가 필요합니다.")
                output.append(token)
                expects_operand = False
            elif token == "(":
                if not expects_operand:
                    raise ExpressionError("여는 괄호 앞에 AND 또는 OR가 필요합니다.")
                stack.append(token)
            elif token == ")":
                if expects_operand:
                    raise ExpressionError("닫는 괄호 앞에 조건이 필요합니다.")
                while stack and stack[-1] != "(":
                    output.append(stack.pop())
                if not stack:
                    raise ExpressionError("괄호 짝이 맞지 않습니다.")
                stack.pop()
                expects_operand = False
            else:
                if expects_operand:
                    raise ExpressionError(f"{token} 앞에 조건이 필요합니다.")
                while stack and stack[-1] in precedence and precedence[stack[-1]] >= precedence[token]:
                    output.append(stack.pop())
                stack.append(token)
                expects_operand = True
        if expects_operand:
            raise ExpressionError("조건 조합이 연산자로 끝납니다.")
        while stack:
            token = stack.pop()
            if token == "(":
                raise ExpressionError("괄호 짝이 맞지 않습니다.")
            output.append(token)
        return output

    @classmethod
    def evaluate(cls, expression: str, values: dict[str, bool]) -> bool:
        stack: list[bool] = []
        for token in cls.to_rpn(expression):
            if token in {"AND", "OR"}:
                if len(stack) < 2:
                    raise ExpressionError("조건 조합이 올바르지 않습니다.")
                right, left = stack.pop(), stack.pop()
                stack.append(left and right if token == "AND" else left or right)
            else:
                if token not in values:
                    raise ExpressionError(f"조건 {token}의 평가값이 없습니다.")
                stack.append(values[token])
        if len(stack) != 1:
            raise ExpressionError("조건 조합이 올바르지 않습니다.")
        return stack[0]

    @classmethod
    def evaluate_status(cls, expression: str, values: dict[str, str]) -> str:
        """Evaluate PASS/FAIL/DATA_INCOMPLETE without letting missing data mask a decisive branch."""
        stack: list[str] = []
        for token in cls.to_rpn(expression):
            if token in {"AND", "OR"}:
                if len(stack) < 2:
                    raise ExpressionError("조건 조합이 올바르지 않습니다.")
                right, left = stack.pop(), stack.pop()
                if token == "AND":
                    stack.append("FAIL" if "FAIL" in {left, right} else "DATA_INCOMPLETE" if "DATA_INCOMPLETE" in {left, right} else "PASS")
                else:
                    stack.append("PASS" if "PASS" in {left, right} else "DATA_INCOMPLETE" if "DATA_INCOMPLETE" in {left, right} else "FAIL")
            else:
                if token not in values:
                    raise ExpressionError(f"조건 {token}의 평가값이 없습니다.")
                stack.append(values[token])
        if len(stack) != 1:
            raise ExpressionError("조건 조합이 올바르지 않습니다.")
        return stack[0]


class DrctRuleValidator:
    PARAM_KEYS = {
        "MARKET_CAP_COMPARE": {"operator", "value"},
        "PRICE_COMPARE_VALUE": {"price_field", "offset", "operator", "value"},
        "PRICE_COMPARE_PRICE": {"lhs", "rhs", "operator"},
        "MA_COMPARE": {"lhs_period", "lhs_offset", "rhs_period", "rhs_offset", "operator"},
        "PRICE_MA_COMPARE": {"price_field", "price_offset", "ma_period", "ma_offset", "operator"},
        "MA_TREND": {"ma_period", "direction", "count", "offset"},
        "CROSS_UP": {"lhs", "rhs"}, "CROSS_DOWN": {"lhs", "rhs"},
        "PCT_CHANGE": {"lhs", "rhs", "operator", "value"},
        "DISTANCE_PCT": {"lhs", "rhs", "operator", "value"},
        "PERIOD_EXISTS_PRICE_CHANGE": {"price_field", "lookback", "operator", "value"},
        "PERIOD_VALUE_COMPARE": {"value_field", "lookback", "operator", "value"},
    }

    @classmethod
    def durable_rule(cls, rule: dict[str, Any]) -> dict[str, Any]:
        schema_version = rule.get("schema_version", 1)
        conditions = []
        for source in rule.get("conditions", []):
            if schema_version == 2:
                predicates = []
                for predicate in source.get("predicates", []):
                    durable = cls._durable_predicate(predicate)
                    if durable is not None:
                        predicates.append(durable)
                conditions.append({
                    "code": source.get("code"), "label": source.get("label"),
                    "source_text": source.get("source_text"), "join": source.get("join", "AND"),
                    "configured": source.get("configured", True), "predicates": predicates,
                })
            else:
                durable = cls._durable_predicate(source)
                if durable is not None:
                    conditions.append({"code": source.get("code"), **durable})
        return {"schema_version": schema_version, "conditions": conditions, "expression": rule.get("expression", "")}

    @classmethod
    def _durable_predicate(cls, source: dict[str, Any]) -> dict[str, Any] | None:
        condition_type = source.get("type")
        if not condition_type:
            return None
        source_params = source.get("params") if isinstance(source.get("params"), dict) else {}
        params: dict[str, Any] = {}
        for key in cls.PARAM_KEYS.get(condition_type, set()):
            if key not in source_params:
                continue
            value = source_params[key]
            if key in {"lhs", "rhs"} and isinstance(value, dict):
                value = {operand_key: value[operand_key] for operand_key in ("kind", "field", "period", "offset") if operand_key in value}
            params[key] = value
        return {"type": condition_type, "label": source.get("label"), "configured": source.get("configured", True), "params": params}

    @staticmethod
    def capabilities() -> dict[str, Any]:
        return {
            "schema_versions": [1, 2],
            "condition_types": sorted(SUPPORTED_CONDITION_TYPES),
            "operators": sorted(SUPPORTED_OPERATORS),
            "price_fields": sorted(SUPPORTED_PRICE_FIELDS),
            "value_fields": sorted(SUPPORTED_VALUE_FIELDS),
            "ma_periods": sorted(SUPPORTED_MA_PERIODS),
            "offset_convention": "0은 분석 기준일, 양수 N은 N거래봉 전",
        }

    @staticmethod
    def _integer(params: dict[str, Any], key: str, errors: list[str], minimum: int = 0) -> int:
        value = params.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            errors.append(f"{key}는 {minimum} 이상의 정수여야 합니다.")
            return 0
        return value

    @staticmethod
    def _number(params: dict[str, Any], key: str, errors: list[str]) -> None:
        value = params.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
            errors.append(f"{key}는 유효한 숫자여야 합니다.")

    @classmethod
    def _operator(cls, params: dict[str, Any], errors: list[str]) -> None:
        if params.get("operator") not in SUPPORTED_OPERATORS:
            errors.append("지원하지 않는 operator입니다.")

    @classmethod
    def _ma(cls, params: dict[str, Any], key: str, errors: list[str]) -> None:
        if params.get(key) not in SUPPORTED_MA_PERIODS:
            errors.append(f"{key}는 지원 MA 기간(5/10/20/60/120/240)이어야 합니다.")

    @classmethod
    def _operand(cls, value: Any, errors: list[str], name: str) -> int:
        if not isinstance(value, dict):
            errors.append(f"{name} 피연산자가 필요합니다.")
            return 0
        kind = value.get("kind")
        offset = value.get("offset", 0)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            errors.append(f"{name}.offset은 0 이상의 정수여야 합니다.")
            offset = 0
        if kind == "PRICE":
            if value.get("field") not in SUPPORTED_PRICE_FIELDS:
                errors.append(f"{name}.field가 지원 가격 필드가 아닙니다.")
        elif kind == "MA":
            if value.get("period") not in SUPPORTED_MA_PERIODS:
                errors.append(f"{name}.period가 지원 MA 기간이 아닙니다.")
        else:
            errors.append(f"{name}.kind는 PRICE 또는 MA여야 합니다.")
        return offset

    @classmethod
    def _condition(cls, condition: dict[str, Any]) -> tuple[list[str], int]:
        errors: list[str] = []
        params = condition.get("params")
        if condition.get("configured", True) is False:
            return ["조건이 구성되지 않았습니다."], 0
        if not isinstance(params, dict):
            return ["params 객체가 필요합니다."], 0
        condition_type = condition.get("type")
        lookback = 0
        if condition_type not in SUPPORTED_CONDITION_TYPES:
            return ["지원하지 않는 Condition Type입니다."], 0
        if condition_type == "MARKET_CAP_COMPARE":
            cls._operator(params, errors); cls._number(params, "value", errors)
        elif condition_type == "PRICE_COMPARE_VALUE":
            if params.get("price_field") not in SUPPORTED_PRICE_FIELDS: errors.append("지원하지 않는 price_field입니다.")
            lookback = cls._integer(params, "offset", errors); cls._operator(params, errors); cls._number(params, "value", errors)
        elif condition_type == "PRICE_COMPARE_PRICE":
            lookback = max(cls._operand(params.get("lhs"), errors, "lhs"), cls._operand(params.get("rhs"), errors, "rhs")); cls._operator(params, errors)
        elif condition_type == "MA_COMPARE":
            cls._ma(params, "lhs_period", errors); cls._ma(params, "rhs_period", errors); cls._operator(params, errors)
            lookback = max(cls._integer(params, "lhs_offset", errors), cls._integer(params, "rhs_offset", errors))
        elif condition_type == "PRICE_MA_COMPARE":
            if params.get("price_field") not in SUPPORTED_PRICE_FIELDS: errors.append("지원하지 않는 price_field입니다.")
            cls._ma(params, "ma_period", errors); cls._operator(params, errors)
            lookback = max(cls._integer(params, "price_offset", errors), cls._integer(params, "ma_offset", errors))
        elif condition_type == "MA_TREND":
            cls._ma(params, "ma_period", errors)
            if params.get("direction") not in {"UP", "DOWN"}: errors.append("direction은 UP 또는 DOWN이어야 합니다.")
            count = cls._integer(params, "count", errors, 1); offset = cls._integer(params, "offset", errors)
            lookback = offset + count
        elif condition_type in {"CROSS_UP", "CROSS_DOWN", "PCT_CHANGE", "DISTANCE_PCT"}:
            lookback = max(cls._operand(params.get("lhs"), errors, "lhs"), cls._operand(params.get("rhs"), errors, "rhs"))
            if condition_type in {"CROSS_UP", "CROSS_DOWN"}: lookback += 1
            else: cls._operator(params, errors); cls._number(params, "value", errors)
        elif condition_type == "PERIOD_EXISTS_PRICE_CHANGE":
            if params.get("price_field", "CLOSE") not in SUPPORTED_PRICE_FIELDS: errors.append("지원하지 않는 price_field입니다.")
            lookback = cls._integer(params, "lookback", errors, 1); cls._operator(params, errors); cls._number(params, "value", errors)
        elif condition_type == "PERIOD_VALUE_COMPARE":
            if params.get("value_field") not in SUPPORTED_VALUE_FIELDS: errors.append("value_field는 VOLUME 또는 TRADING_VALUE여야 합니다.")
            lookback = max(0, cls._integer(params, "lookback", errors, 1) - 1); cls._operator(params, errors); cls._number(params, "value", errors)
        return errors, lookback

    @classmethod
    def validate(cls, rule: dict[str, Any]) -> RuleValidationResult:
        errors: list[dict[str, str]] = []
        schema_version = rule.get("schema_version")
        if schema_version not in {1, 2}:
            errors.append({"code": "SCHEMA_VERSION", "message": "지원하는 Rule 형식은 v1과 v2입니다."})
        conditions = rule.get("conditions")
        expression = rule.get("expression")
        if not isinstance(conditions, list) or not conditions:
            status = "DRAFT" if not conditions and not str(expression or "").strip() else "INVALID"
            return RuleValidationResult(status, [{"code": "CONDITIONS", "message": "하나 이상의 조건이 필요합니다."}], 0)
        codes: list[str] = []
        lookback = 0
        for index, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                errors.append({"code": "CONDITION", "message": f"{index + 1}번째 조건 형식이 올바르지 않습니다."}); continue
            code = str(condition.get("code", "")).upper()
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", code):
                errors.append({"code": "CONDITION_CODE", "message": f"조건 코드 {code or '(없음)'}가 올바르지 않습니다."})
            codes.append(code)
            if schema_version == 2:
                if condition.get("join") not in {"AND", "OR"}:
                    errors.append({"code": code or "CONDITION", "message": f"조건 {code}: 조건 내부 연결 방식이 올바르지 않습니다."})
                predicates = condition.get("predicates")
                condition_errors: list[str] = []
                condition_lookback = 0
                if condition.get("configured", True) is False or not isinstance(predicates, list) or not predicates:
                    condition_errors.append("조건이 완성되지 않았습니다.")
                else:
                    for predicate in predicates:
                        predicate_errors, predicate_lookback = cls._condition(predicate)
                        condition_errors.extend(predicate_errors)
                        condition_lookback = max(condition_lookback, predicate_lookback)
            else:
                condition_errors, condition_lookback = cls._condition(condition)
            lookback = max(lookback, condition_lookback)
            errors.extend({"code": code or "CONDITION", "message": f"조건 {code or index + 1}: {message}"} for message in condition_errors)
        duplicates = sorted({code for code in codes if codes.count(code) > 1})
        for code in duplicates:
            errors.append({"code": "DUPLICATE_CODE", "message": f"조건 코드 {code}가 중복되었습니다."})
        try:
            referenced = {token for token in BooleanExpression.to_rpn(str(expression or "")) if token not in {"AND", "OR"}}
            for code in sorted(referenced - set(codes)):
                errors.append({"code": "UNKNOWN_CODE", "message": f"조건 조합에서 존재하지 않는 {code}를 참조합니다."})
        except ExpressionError as exc:
            errors.append({"code": "EXPRESSION", "message": str(exc)})
        return RuleValidationResult("INVALID" if errors else "VALID", errors, lookback)


class DrctRuleEvaluator:
    PRICE_COLUMN = {"OPEN": "open_price", "HIGH": "high_price", "LOW": "low_price", "CLOSE": "close_price"}
    VALUE_COLUMN = {"VOLUME": "volume", "TRADING_VALUE": "trading_value"}

    @staticmethod
    def _compare(left: float, operator: str, right: float) -> bool:
        functions: dict[str, Callable[[float, float], bool]] = {
            "GT": lambda a, b: a > b, "GTE": lambda a, b: a >= b,
            "LT": lambda a, b: a < b, "LTE": lambda a, b: a <= b, "EQ": lambda a, b: a == b,
        }
        return functions[operator](left, right)

    @classmethod
    def _row_value(cls, rows: list[dict[str, Any]], offset: int, column: str) -> float:
        if offset >= len(rows) or rows[offset].get(column) is None:
            raise DataIncompleteError(f"{offset}봉전 {column} 데이터가 없습니다.")
        return float(rows[offset][column])

    @classmethod
    def _operand(cls, rows: list[dict[str, Any]], operand: dict[str, Any], extra_offset: int = 0) -> float:
        offset = int(operand.get("offset", 0)) + extra_offset
        if operand["kind"] == "PRICE":
            return cls._row_value(rows, offset, cls.PRICE_COLUMN[operand["field"]])
        return cls._row_value(rows, offset, f"ma{int(operand['period'])}")

    @staticmethod
    def _fmt(value: float) -> str:
        return f"{value:,.4f}".rstrip("0").rstrip(".")

    @classmethod
    def evaluate_condition(cls, condition: dict[str, Any], rows: list[dict[str, Any]], market_cap: int | None) -> dict[str, Any]:
        code, kind, params = condition["code"], condition["type"], condition["params"]
        try:
            actual: float | list[float]
            criteria = kind
            if kind == "MARKET_CAP_COMPARE":
                if market_cap is None: raise DataIncompleteError("분석일 시장가치 데이터가 없습니다.")
                actual = float(market_cap); passed = cls._compare(actual, params["operator"], float(params["value"])); criteria = f"시장가치 {params['operator']} {params['value']}"
            elif kind == "PRICE_COMPARE_VALUE":
                actual = cls._row_value(rows, params["offset"], cls.PRICE_COLUMN[params["price_field"]]); passed = cls._compare(actual, params["operator"], float(params["value"])); criteria = f"{params['price_field']} {params['offset']}봉전 {params['operator']} {params['value']}"
            elif kind == "PRICE_COMPARE_PRICE":
                left, right = cls._operand(rows, params["lhs"]), cls._operand(rows, params["rhs"]); actual = [left, right]; passed = cls._compare(left, params["operator"], right); criteria = f"가격 비교 {params['operator']}"
            elif kind == "MA_COMPARE":
                left = cls._row_value(rows, params["lhs_offset"], f"ma{params['lhs_period']}"); right = cls._row_value(rows, params["rhs_offset"], f"ma{params['rhs_period']}"); actual = [left, right]; passed = cls._compare(left, params["operator"], right); criteria = f"MA{params['lhs_period']} {params['operator']} MA{params['rhs_period']}"
            elif kind == "PRICE_MA_COMPARE":
                left = cls._row_value(rows, params["price_offset"], cls.PRICE_COLUMN[params["price_field"]]); right = cls._row_value(rows, params["ma_offset"], f"ma{params['ma_period']}"); actual = [left, right]; passed = cls._compare(left, params["operator"], right); criteria = f"{params['price_field']} {params['operator']} MA{params['ma_period']}"
            elif kind == "MA_TREND":
                values = [cls._row_value(rows, params.get("offset", 0) + index, f"ma{params['ma_period']}") for index in range(params["count"] + 1)]; actual = values
                passed = all(values[i] > values[i + 1] for i in range(params["count"])) if params["direction"] == "UP" else all(values[i] < values[i + 1] for i in range(params["count"])); criteria = f"MA{params['ma_period']} {params['direction']} {params['count']}회"
            elif kind in {"CROSS_UP", "CROSS_DOWN"}:
                current_left, current_right = cls._operand(rows, params["lhs"]), cls._operand(rows, params["rhs"])
                prior_left, prior_right = cls._operand(rows, params["lhs"], 1), cls._operand(rows, params["rhs"], 1)
                actual = [prior_left, prior_right, current_left, current_right]
                passed = prior_left <= prior_right and current_left > current_right if kind == "CROSS_UP" else prior_left >= prior_right and current_left < current_right
                criteria = kind
            elif kind == "PCT_CHANGE":
                start, end = cls._operand(rows, params["lhs"]), cls._operand(rows, params["rhs"])
                if start == 0: raise DataIncompleteError("변화율 기준값이 0입니다.")
                actual = (end - start) / abs(start) * 100; passed = cls._compare(actual, params["operator"], float(params["value"])); criteria = f"변화율 {params['operator']} {params['value']}%"
            elif kind == "DISTANCE_PCT":
                left, right = cls._operand(rows, params["lhs"]), cls._operand(rows, params["rhs"])
                if right == 0: raise DataIncompleteError("이격률 기준값이 0입니다.")
                actual = abs(left - right) / abs(right) * 100; passed = cls._compare(actual, params["operator"], float(params["value"])); criteria = f"절대 이격률 {params['operator']} {params['value']}%"
            elif kind == "PERIOD_EXISTS_PRICE_CHANGE":
                changes = []
                column = cls.PRICE_COLUMN[params.get("price_field", "CLOSE")]
                for offset in range(params["lookback"]):
                    previous = cls._row_value(rows, offset + 1, "close_price")
                    current = cls._row_value(rows, offset, column)
                    if previous == 0: raise DataIncompleteError("등락률 기준 종가가 0입니다.")
                    changes.append((current - previous) / abs(previous) * 100)
                actual = changes; passed = any(cls._compare(value, params["operator"], float(params["value"])) for value in changes); criteria = f"최근 {params['lookback']}봉 가격변화 존재"
            else:
                values = [cls._row_value(rows, offset, cls.VALUE_COLUMN[params["value_field"]]) for offset in range(params["lookback"])]
                actual = values; passed = any(cls._compare(value, params["operator"], float(params["value"])) for value in values); criteria = f"최근 {params['lookback']}봉 {params['value_field']} 조건 존재"
            actual_text = ", ".join(cls._fmt(value) for value in actual) if isinstance(actual, list) else cls._fmt(actual)
            return {"code": code, "type": kind, "label": condition.get("label") or code, "status": "PASS" if passed else "FAIL", "criteria": criteria, "actual_value": actual_text}
        except DataIncompleteError as exc:
            return {"code": code, "type": kind, "label": condition.get("label") or code, "status": "DATA_INCOMPLETE", "criteria": kind, "actual_value": str(exc)}

    @classmethod
    def evaluate(cls, rule: dict[str, Any], rows: list[dict[str, Any]], market_cap: int | None) -> dict[str, Any]:
        if rule.get("schema_version") == 2:
            diagnostics = [cls.evaluate_group(condition, rows, market_cap) for condition in rule["conditions"]]
        else:
            diagnostics = [cls.evaluate_condition(condition, rows, market_cap) for condition in rule["conditions"]]
        expression_status = BooleanExpression.evaluate_status(rule["expression"], {item["code"]: item["status"] for item in diagnostics})
        status = {"PASS": "MATCH", "FAIL": "NO_MATCH", "DATA_INCOMPLETE": "DATA_INCOMPLETE"}[expression_status]
        return {"status": status, "conditions": diagnostics}

    @classmethod
    def evaluate_group(cls, group: dict[str, Any], rows: list[dict[str, Any]], market_cap: int | None) -> dict[str, Any]:
        items = []
        for index, predicate in enumerate(group.get("predicates", []), start=1):
            items.append(cls.evaluate_condition({"code": f"{group['code']}_{index}", **predicate}, rows, market_cap))
        join = group.get("join", "AND")
        statuses = [item["status"] for item in items]
        if join == "AND":
            status = "FAIL" if "FAIL" in statuses else "DATA_INCOMPLETE" if "DATA_INCOMPLETE" in statuses else "PASS"
        else:
            status = "PASS" if "PASS" in statuses else "DATA_INCOMPLETE" if "DATA_INCOMPLETE" in statuses else "FAIL"
        return {
            "code": group["code"], "type": "CONDITION_GROUP", "label": group.get("label") or group["code"],
            "status": status,
            "criteria": " 그리고 ".join(item["criteria"] for item in items) if join == "AND" else " 또는 ".join(item["criteria"] for item in items),
            "actual_value": " / ".join(item["actual_value"] for item in items),
        }
