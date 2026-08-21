# 미국 시장 테마 관리 Phase 1

## 범위

Phase 1은 미국 종목 Universe를 미국 테마그룹·테마에 연결하고, 연결 종목의 역할과 대표 여부를 관리하며 네이버 일봉·주봉·월봉 이미지를 확인하는 단계다. 미국 OHLCV, 테마등락률, 수급, 관찰우선순위, 추천후보, 한·미 테마 매핑은 포함하지 않는다.

기존 `market_theme_groups`/`market_themes` 계열과 KRX 종목·차트·계산 API는 변경하지 않는다. 미국 데이터는 별도 테이블과 `/us-market-themes` API를 사용한다.

## 화면 구조와 시장 Scope

- `/market-themes?market=kr`: 기존 국내 테마 기능 전체
- `/market-themes?market=us`: 미국 Phase 1
- 잘못되거나 없는 `market` 값은 국내로 처리한다.
- 업무 탭과 시장 Scope 패널은 데스크톱에서 80:20, 900px 이하에서 1열이다.
- 미국 업무 탭은 `테마 관리`, `종목 연결`만 제공한다.
- 미국 테마 하위 탭은 `테마그룹별`, `테마별`만 제공한다.
- 미국 Summary는 테마그룹, 전체 테마, 활성 테마, 연결 종목만 표시한다.

## DB 구조

### `us_theme_groups`

이름, 설명, 정렬, 활성 상태와 생성·수정 시각을 저장한다. `name`은 UNIQUE다.

### `us_themes`

`theme_group_id`로 그룹을 참조하고 이름, 설명, 키워드, 정렬, 활성 상태를 저장한다. `(theme_group_id, name)`은 UNIQUE다. 키워드는 사용자가 입력한 정형 문자열 목록만 줄 단위 TEXT로 저장하며 외부 응답 JSON은 저장하지 않는다.

### `us_theme_stocks`

`theme_id`와 `us_stock_id`의 N:M 관계다. `(theme_id, us_stock_id)`는 UNIQUE이며 같은 종목은 서로 다른 테마에 연결할 수 있다. 해제는 관계의 `active`만 0으로 바꾸므로 `us_stocks` 종목은 유지된다.

역할은 `LEADER`, `CORE`, `RELATED`, `ETF`를 지원한다. `is_representative`는 역할과 독립적으로 관리한다.

## API

- `GET /us-market-themes/summary`
- `GET|POST /us-market-themes/groups`
- `PATCH /us-market-themes/groups/{id}`
- `GET|POST /us-market-themes/themes`
- `PATCH /us-market-themes/themes/{id}`
- `GET|POST /us-market-themes/themes/{id}/stocks`
- `PATCH|DELETE /us-market-themes/mappings/{id}`
- `GET /us-stocks/{id}/naver-charts`

목록·상세 응답은 명시 필드만 반환하며 내부 JSON blob은 노출하지 않는다.

## 네이버 차트 조회

백엔드는 DB에 등록된 `us_stocks.naver_code`만 사용해 다음 Endpoint를 한 번 조회한다.

```text
https://api.stock.naver.com/stock/{naver_code}/basic
```

응답 중 아래 URL만 추출한다.

```text
imageChartUrlInfo.candle.day
imageChartUrlInfo.candle.week
imageChartUrlInfo.candle.month
```

원본 응답, 이미지 URL, 가격값은 DB나 localStorage에 저장하지 않는다. 백엔드 프로세스 메모리에 `naver_code`별 20분 캐시만 둔다. 프런트엔드는 행이 화면 근처에 진입할 때 종목당 API 한 번을 요청하고 이미지에는 lazy loading을 적용한다.

`naver_code` 누락, HTTP 오류, timeout, JSON 구조 변경, 일부 URL 누락은 개별 차트의 `차트없음` 또는 `조회불가` 상태로 처리하며 화면 전체를 실패시키지 않는다. 네이버 이미지는 시각 확인용이며 분석 가격 데이터로 사용하지 않는다.

## 실패 및 데이터 보호 정책

- 그룹과 테마 삭제보다 비활성화를 우선한다.
- 종목 연결 해제는 관계만 비활성화한다.
- Seed 데이터는 삽입하지 않는다.
- 미국 기능은 국내 테마 테이블과 계산 결과를 읽거나 수정하지 않는다.
- Raw Naver JSON과 재현 가능한 차트 URL은 영속화하지 않는다.

## 다음 단계

Phase 2에서 검증된 가격 공급자를 통해 `us_stock_daily_prices`, 과거가격 수집, 미국 테마 일별 등락률과 테마강도를 구현한다. 네이버 이미지는 Phase 2에서도 가격 Source로 사용하지 않는다.
