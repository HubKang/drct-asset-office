from __future__ import annotations

import json

DEFAULT_MARKET_THEMES: list[dict[str, object]] = [
    {"theme_name": "AI", "theme_code": "ai", "theme_type": "theme", "description": "AI 관련 시장 테마", "keywords": ["AI", "인공지능", "생성형AI", "데이터센터", "GPU", "LLM", "AI반도체"], "sort_order": 1},
    {"theme_name": "반도체", "theme_code": "semiconductor", "theme_type": "theme", "description": "반도체 관련 시장 테마", "keywords": ["반도체", "메모리", "파운드리", "HBM", "시스템반도체", "장비"], "sort_order": 2},
    {"theme_name": "전력기기", "theme_code": "power_equipment", "theme_type": "theme", "description": "전력기기 관련 시장 테마", "keywords": ["전력기기", "변압기", "송전", "배전", "전력망", "HVDC", "초고압", "변전소", "전선"], "sort_order": 3},
    {"theme_name": "전력망", "theme_code": "power_grid", "theme_type": "theme", "description": "전력망 관련 시장 테마", "keywords": ["전력망", "송전망", "배전망", "변전", "HVDC"], "sort_order": 4},
    {"theme_name": "변압기", "theme_code": "transformer", "theme_type": "theme", "description": "변압기 관련 시장 테마", "keywords": ["변압기", "초고압", "배전변압기", "송전"], "sort_order": 5},
    {"theme_name": "방산", "theme_code": "defense", "theme_type": "theme", "description": "방위산업 관련 시장 테마", "keywords": ["방산", "방위산업", "무기체계", "미사일", "장갑차", "K9", "국방", "수출계약"], "sort_order": 6},
    {"theme_name": "조선", "theme_code": "shipbuilding", "theme_type": "theme", "description": "조선 관련 시장 테마", "keywords": ["조선", "선박", "LNG선", "해양플랜트"], "sort_order": 7},
    {"theme_name": "로봇", "theme_code": "robot", "theme_type": "theme", "description": "로봇 관련 시장 테마", "keywords": ["로봇", "협동로봇", "자동화", "휴머노이드"], "sort_order": 8},
    {"theme_name": "바이오", "theme_code": "bio", "theme_type": "theme", "description": "바이오 관련 시장 테마", "keywords": ["바이오", "임상", "신약", "FDA", "품목허가", "항암제", "치료제"], "sort_order": 9},
    {"theme_name": "원전", "theme_code": "nuclear_power", "theme_type": "theme", "description": "원전 관련 시장 테마", "keywords": ["원전", "원자력", "SMR", "원전수출"], "sort_order": 10},
    {"theme_name": "2차전지", "theme_code": "secondary_battery", "theme_type": "theme", "description": "2차전지 관련 시장 테마", "keywords": ["2차전지", "배터리", "양극재", "음극재", "전해질"], "sort_order": 11},
    {"theme_name": "데이터센터", "theme_code": "data_center", "theme_type": "theme", "description": "데이터센터 관련 시장 테마", "keywords": ["데이터센터", "서버", "전력수요", "냉각"], "sort_order": 12},
    {"theme_name": "우주항공", "theme_code": "aerospace", "theme_type": "theme", "description": "우주항공 관련 시장 테마", "keywords": ["우주항공", "위성", "발사체", "항공엔진"], "sort_order": 13},
    {"theme_name": "화장품", "theme_code": "cosmetics", "theme_type": "theme", "description": "화장품 관련 시장 테마", "keywords": ["화장품", "K뷰티", "면세", "수출"], "sort_order": 14},
    {"theme_name": "엔터", "theme_code": "entertainment", "theme_type": "theme", "description": "엔터테인먼트 관련 시장 테마", "keywords": ["엔터", "콘서트", "음반", "IP"], "sort_order": 15},
    {"theme_name": "자동차부품", "theme_code": "auto_parts", "theme_type": "theme", "description": "자동차부품 관련 시장 테마", "keywords": ["자동차부품", "전장", "모듈", "완성차공급"], "sort_order": 16},
]


def keywords_json(keywords: list[str]) -> str:
    return json.dumps(keywords, ensure_ascii=False)

