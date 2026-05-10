# 데이터 모델 가이드

## 1. 데이터모델 설계 원칙
- SQLite 파일은 `db/drct_asset.sqlite3`를 사용한다.
- 스키마 단일 기준은 `backend/app/sql/schema.sql`이다.
- 날짜/시간은 ISO 문자열 `TEXT`로 저장한다.
- 원문은 BLOB이 아닌 파일 경로 컬럼으로 관리한다.

## 2. 테이블 목록
- stocks
- watchlist
- news_items
- disclosures
- price_daily
- research_reports
- gpt_advisories
- investment_decisions
- risk_reviews
- trade_reviews
- collection_runs
- analysis_source_items
- schema_comments

## 3. 테이블별 역할
- stocks: 종목 마스터
- watchlist: 관심종목 관리
- news_items: 뉴스 수집/요약
- disclosures: 공시 수집/요약
- price_daily: 일봉 시세
- research_reports: 리서치 보고서 메타정보
- gpt_advisories: GPT 자문 결과
- investment_decisions: 투자 의사결정 기록
- risk_reviews: 리스크 리뷰
- trade_reviews: 매매 복기
- collection_runs: 수집 실행 로그
- analysis_source_items: 리포트 생성 시 사용된 근거 자료(뉴스/공시) 추적
- schema_comments: 한글 설명 메타데이터

## 4. 테이블별 한글 설명
| 테이블 | 설명 |
|---|---|
| stocks | 종목 마스터 정보 |
| watchlist | 관심종목 관리 정보 |
| news_items | 뉴스 수집 및 요약 정보 |
| disclosures | 공시 수집 및 요약 정보 |
| price_daily | 일별 시세 정보 |
| research_reports | 리서치 보고서 메타정보 |
| gpt_advisories | GPT 자문 결과 정보 |
| investment_decisions | 투자 의사결정 기록 |
| risk_reviews | 리스크 점검 기록 |
| trade_reviews | 매매 복기 기록 |
| collection_runs | 수집 작업 실행 이력 |
| analysis_source_items | 리포트 근거 자료 추적 정보 |
| schema_comments | 테이블/컬럼 한글 설명 메타데이터 |

## 5. 컬럼별 한글 설명

### stocks
| 컬럼 | 설명 |
|---|---|
| id | 종목 PK |
| stock_code | 종목 코드 |
| stock_name | 종목명 |
| market | 시장 구분 |
| sector | 섹터 |
| industry | 업종 |
| is_active | 활성 여부(1:활성, 0:비활성) |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |
| updated_at | 수정 시각(YYYY-MM-DD HH:MM:SS) |

### watchlist
| 컬럼 | 설명 |
|---|---|
| id | 관심종목 PK |
| stock_id | 종목 FK |
| status | 관심 상태 |
| interest_reason | 관심 사유 |
| entry_condition | 진입 조건 |
| exit_condition | 이탈 조건 |
| risk_note | 리스크 메모 |
| registered_at | 등록 시각(YYYY-MM-DD HH:MM:SS) |
| updated_at | 수정 시각(YYYY-MM-DD HH:MM:SS) |

### news_items
| 컬럼 | 설명 |
|---|---|
| id | 뉴스 PK |
| stock_id | 종목 FK(선택) |
| title | 뉴스 제목 |
| source | 뉴스 출처 |
| url | 뉴스 URL |
| published_at | 기사 게시 시각(YYYY-MM-DD HH:MM:SS) |
| collected_at | 수집 시각(YYYY-MM-DD HH:MM:SS) |
| raw_text_path | 원문 파일 경로 |
| summary | 요약 내용 |
| sentiment | 감성 분류 |
| importance_score | 중요도 점수 |
| ai_summary | 로컬 LLM 투자 관점 1건 요약 |
| ai_sentiment | AI 감성 분류(positive/neutral/negative) |
| ai_importance_score | AI 중요도 점수(0~100) |
| ai_tags | AI 태그 목록(문자열) |
| ai_processed_at | AI 처리 시각(YYYY-MM-DD HH:MM:SS) |
| ai_summary_error | AI 요약 실패 메시지 |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### disclosures
| 컬럼 | 설명 |
|---|---|
| id | 공시 PK |
| stock_id | 종목 FK |
| dart_receipt_no | DART 접수번호 |
| disclosure_title | 공시 제목 |
| disclosure_type | 공시 유형 |
| disclosed_at | 공시 시각(YYYY-MM-DD HH:MM:SS) |
| url | 공시 URL |
| raw_text_path | 원문 파일 경로 |
| summary | 요약 내용 |
| importance_score | 중요도 점수 |
| ai_summary | 로컬 LLM 공시 1건 요약 |
| ai_importance_score | AI 중요도 점수(0~100) |
| ai_tags | AI 태그 목록(문자열) |
| ai_risk_level | AI 리스크 수준(low/medium/high/unknown) |
| ai_event_type | AI 이벤트 유형 |
| ai_processed_at | AI 처리 시각(YYYY-MM-DD HH:MM:SS) |
| ai_summary_error | AI 요약 실패 메시지 |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### price_daily
| 컬럼 | 설명 |
|---|---|
| id | 일별시세 PK |
| stock_id | 종목 FK |
| trade_date | 거래일(YYYY-MM-DD) |
| open_price | 시가 |
| high_price | 고가 |
| low_price | 저가 |
| close_price | 종가 |
| volume | 거래량 |
| trading_value | 거래대금 |
| change_rate | 등락률 |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### research_reports
| 컬럼 | 설명 |
|---|---|
| id | 리서치 보고서 PK |
| stock_id | 종목 FK(선택) |
| report_type | 보고서 유형 |
| title | 보고서 제목 |
| report_date | 보고서 기준일(YYYY-MM-DD HH:MM:SS) |
| summary | 목록 표시용 짧은 요약 |
| markdown_content | Markdown 리포트 전문 |
| markdown_path | 마크다운 파일 경로 |
| generated_by | 생성 주체 |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### gpt_advisories
| 컬럼 | 설명 |
|---|---|
| id | GPT 자문 PK |
| stock_id | 종목 FK(선택) |
| source_report_id | 원본 보고서 FK(선택) |
| prompt_path | 프롬프트 파일 경로 |
| response_path | 응답 파일 경로 |
| advisory_summary | 자문 요약 |
| final_opinion | 최종 의견 |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### investment_decisions
| 컬럼 | 설명 |
|---|---|
| id | 투자결정 PK |
| stock_id | 종목 FK |
| decision_date | 결정일(YYYY-MM-DD HH:MM:SS) |
| decision_type | 결정 유형 |
| reason | 결정 사유 |
| expected_scenario | 기대 시나리오 |
| invalidation_condition | 무효화 조건 |
| stop_loss_condition | 손절 조건 |
| review_date | 재검토일(YYYY-MM-DD HH:MM:SS) |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### risk_reviews
| 컬럼 | 설명 |
|---|---|
| id | 리스크 점검 PK |
| stock_id | 종목 FK |
| report_id | 연결 보고서 FK(선택) |
| risk_level | 리스크 수준 |
| risk_summary | 리스크 요약 |
| buy_prohibited_reason | 매수 금지 사유 |
| stop_loss_condition | 손절 조건 |
| position_size_suggestion | 비중 제안 |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### trade_reviews
| 컬럼 | 설명 |
|---|---|
| id | 매매복기 PK |
| stock_id | 종목 FK |
| decision_id | 투자결정 FK(선택) |
| review_date | 복기일(YYYY-MM-DD HH:MM:SS) |
| result_summary | 결과 요약 |
| what_was_right | 잘한 점 |
| what_was_wrong | 아쉬운 점 |
| lesson_learned | 교훈 |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### collection_runs
| 컬럼 | 설명 |
|---|---|
| id | 수집실행 PK |
| collector_name | 수집기 이름 |
| target | 수집 대상 |
| status | 실행 상태 |
| started_at | 시작 시각(YYYY-MM-DD HH:MM:SS) |
| finished_at | 종료 시각(YYYY-MM-DD HH:MM:SS) |
| message | 실행 메시지 |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

### schema_comments
| 컬럼 | 설명 |
|---|---|
| id | 스키마 코멘트 PK |
| table_name | 설명 대상 테이블명 |
| column_name | 설명 대상 컬럼명(NULL이면 테이블 설명) |
| comment_ko | 한글 설명 |
| created_at | 등록 시각(YYYY-MM-DD HH:MM:SS) |

### analysis_source_items
| 컬럼 | 설명 |
|---|---|
| id | 리포트 근거 자료 PK |
| report_id | 리서치 보고서 FK |
| stock_id | 종목 FK |
| source_type | 근거 자료 유형(news/disclosure) |
| source_id | 근거 자료 원본 ID |
| used_stage | 사용 단계(chunk_summary/final_briefing) |
| created_at | 생성 시각(YYYY-MM-DD HH:MM:SS) |

## 6. 주요 컬럼 설명
- `raw_text_path`, `markdown_path`, `prompt_path`, `response_path`는 파일 경로 저장용
- `research_reports.summary`는 목록용 요약, `research_reports.markdown_content`는 리포트 전문 저장용
- `news_items.summary`는 네이버 API description 정제값, `news_items.ai_summary`는 로컬 LLM 재요약값
- `disclosures.ai_summary`는 로컬 LLM 공시 1건 투자 관점 요약값
- `importance_score`는 정수형 중요도
- 시간 컬럼은 모두 YYYY-MM-DD HH:MM:SS 기준

## 7. 테이블 간 관계
- stocks(1) - watchlist/news_items/disclosures/price_daily/research_reports/investment_decisions/risk_reviews/trade_reviews/gpt_advisories(N)
- research_reports(1) - gpt_advisories(N)
- research_reports(1) - risk_reviews(N)
- investment_decisions(1) - trade_reviews(N)

## 8. UNIQUE 제약
- stocks.stock_code
- news_items.url
- disclosures.dart_receipt_no
- price_daily(stock_id, trade_date)
- analysis_source_items(stock_id, source_type, source_id)
- schema_comments(table_name, column_name)

## 9. 파일 저장 정책
- DB 파일: `db/drct_asset.sqlite3`
- 원문/리포트/응답 본문은 파일로 저장하고 DB는 경로만 저장

## 10. schema_comments 테이블 사용 방식
- SQLite의 COMMENT ON TABLE/COLUMN 미지원 보완용 메타테이블
- 테이블 설명: `column_name = NULL`
- 컬럼 설명: `column_name = 컬럼명`
- 등록 SQL은 `INSERT OR IGNORE`로 재실행 시 중복 오류 방지
- 대시보드 데이터사전/정의서 표시의 기반 데이터로 활용

## 11. 향후 PostgreSQL 전환 시 고려사항
- 시간 타입을 TIMESTAMPTZ로 전환 검토
- ENUM/체크 제약 강화
- Alembic 기반 마이그레이션 체계로 확장


## 일시 저장 형식 표준
- 모든 일시 컬럼은 TEXT 타입으로 저장한다.
- 저장 형식은 YYYY-MM-DD HH:MM:SS를 사용한다.
- 날짜 전용 컬럼은 YYYY-MM-DD 형식을 유지한다.
- 예: 	rade_date, decision_date, eview_date, eport_date`n

## classification_rules (10E)
- 목적: 뉴스/공시 ai_summary를 기반으로 태그·감성·중요도·리스크/이벤트 분류 규칙을 DB에서 관리
- 주요 컬럼
  - rule_group: tag / sentiment / importance / disclosure_event_type / disclosure_risk_level
  - target_type: news / disclosure
  - keywords: 쉼표 구분 키워드
  - output_field: ai_tags / ai_sentiment / ai_importance_score / ai_event_type / ai_risk_level
  - output_value: 규칙 매칭 시 반영값
  - score_delta: 중요도 점수 가감
  - priority: 숫자 작을수록 우선
  - is_active: 1 사용, 0 미사용

### 규칙 적용 방식
- 뉴스: title + summary + ai_summary 텍스트에 대해 active news 규칙 적용
- 공시: disclosure_title + disclosure_type + ai_summary 텍스트에 대해 active disclosure 규칙 적용
- ai_summary는 변경하지 않고 분류 컬럼만 보완

### API
- GET /classification-rules
- GET /classification-rules/{rule_id}
- POST /classification-rules
- PATCH /classification-rules/{rule_id}
- POST /classification-rules/{rule_id}/deactivate
- POST /analysis/news/classify
- POST /analysis/disclosures/classify
- POST /analysis/source-items/classify
