from __future__ import annotations

DEFAULT_GPT_PROMPTS: list[dict[str, object]] = [
    {
        "domain": "investment_advisory",
        "prompt_key": "stock_advisory_analysis",
        "prompt_name": "종목 분석 프롬프트",
        "description": "기존 종목 분석 요청문",
        "sort_order": 10,
        "default_prompt_text": "입력된 종목 근거 데이터를 기반으로 리스크를 포함한 분석 요약을 작성하세요.",
    },
    {
        "domain": "trade_review",
        "prompt_key": "trade_single_review",
        "prompt_name": "단건 매매복기",
        "description": "매매일지 1건 기준 복기 분석",
        "sort_order": 10,
        "default_prompt_text": (
            "당신은 데이터 기반 주식 매매 복기 코치입니다.\n"
            "아래 DrCT에셋 매매복기 패키지를 바탕으로 사용자의 매매 판단 과정과 결과를 객관적으로 분석해 주세요.\n"
            "수익 여부보다 매매 원칙 준수 여부를 우선 평가해 주세요.\n"
            "기록에 없는 사실은 추정하지 말고, 데이터가 부족한 항목은 추가 확인 필요로 표시해 주세요.\n"
            "자동 매수/매도 판단이나 향후 종목 추천은 하지 마세요.\n\n"
            "분석 출력은 다음 순서를 따라주세요.\n"
            "1) 원칙 준수 평가\n2) 진입/청산 타이밍 복기\n3) 실패/리스크 패턴\n4) 다음 매매 체크리스트"
        ),
    },
    {
        "domain": "trade_review",
        "prompt_key": "trade_monthly_review",
        "prompt_name": "월간 매매복기",
        "description": "월 단위 매매 성과와 패턴 분석",
        "sort_order": 20,
        "default_prompt_text": "월간 매매일지 묶음을 기준으로 원칙 준수율, 반복 패턴, 개선 과제를 분석하세요.",
    },
    {
        "domain": "trade_review",
        "prompt_key": "strategy_performance_review",
        "prompt_name": "매매기법별 복기",
        "description": "매매기법별 성과/리스크 분석",
        "sort_order": 30,
        "default_prompt_text": "매매기법별 승률/손익/재현성을 비교하고 유지·보완·중단 권고를 제시하세요.",
    },
    {
        "domain": "trade_review",
        "prompt_key": "failure_pattern_review",
        "prompt_name": "실패 패턴 분석",
        "description": "손실 사례 중심 실패 패턴 분석",
        "sort_order": 40,
        "default_prompt_text": "손실 사례를 중심으로 실패 패턴을 분류하고 재발 방지 체크리스트를 작성하세요.",
    },
]