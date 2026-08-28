# 미국 Daily Price yfinance 운영 정책

## 상태

2026-08-27부터 미국 Daily OHLCV의 운영 Source of Truth는 `yfinance==1.6.0`이다. 최신 종가와 260거래일 과거가격 수집은 모두 yfinance를 사용하며, 실패 시 Kiwoom `usa06012`로 자동 대체하지 않는다. 기존 DB 값은 삭제하지 않고 `(us_stock_id, trade_date)` 기준으로 UPSERT한다.

Kiwoom은 미국 Universe와 종목 관리 등 기존 보조 기능에 계속 사용하지만, 미국 Daily OHLCV 수집 경로에서는 사용하지 않는다.

## 수집 설정

- `interval="1d"`
- `prepost=False`
- `auto_adjust=False`
- `actions=False`
- `repair=False`
- DB에는 `Close`를 포함한 원본 OHLCV를 사용하고 `Adj Close`는 사용하지 않는다.
- 30종목 단위로 조회하고 누락 종목만 최대 2회 개별 재시도한다.
- Yahoo DataFrame과 원본 응답은 저장하거나 전체 로그로 남기지 않는다.
- `BRK.B`, `BF.B`처럼 확인된 class-share 예외만 명시적으로 Yahoo symbol로 변환한다.

## Close 중심 검증과 Open 경계 정규화

다음 오류는 저장을 거부한다.

- 거래일 누락 또는 형식 오류
- OHLC NaN, 무한대 또는 0 이하
- `high < low`
- `close > high` 또는 `close < low`
- `volume < 0`

Close가 정상 범위에 있지만 Open만 범위를 벗어나면 일봉을 버리지 않고 다음처럼 High/Low envelope만 확장한다.

```text
normalized_high = max(raw_high, raw_open, raw_close)
normalized_low  = min(raw_low, raw_open, raw_close)
```

Open, Close, Volume은 변경하지 않는다. 이 경우 Backend diagnostic에는 `NORMALIZED_OPEN_BOUNDARY`만 기록하며 원본 응답은 저장하지 않는다.

## 거래일 완료 정책

Yahoo가 반환하는 실제 거래일만 사용한다. `America/New_York` 기준 같은 날짜의 행은 16:15 이후에만 완료된 일봉 후보로 인정한다. 주말·휴장일 행을 달력 계산으로 만들지 않는다. 최신 수집은 DB에 저장된 최근 실제 거래일 2개부터 겹쳐 조회하여 공급자 정정을 자연스럽게 반영한다.

## 운영 전환 결과

112종목 Dry Run 결과는 정상 107, Open 경계 정규화 5, Critical/Missing/Network 오류 0으로 Gate를 통과했다. 전 종목 최신 거래일은 2026-08-26이었다.

운영 260거래일 UPSERT 결과:

- 활성 종목: 112
- 성공/실패: 112 / 0
- 신규/갱신/동일: 237 / 28,883 / 0
- Open 경계 정규화: 5
- yfinance 저장 행: 29,120
- 영향 기간: 2025-08-13 ~ 2026-08-26
- 활성 미국 테마 재계산: 29
- 최신 미국 테마 거래일: 2026-08-26

검증 사례:

- NVDA 2026-08-26: O 212.42 / H 213.60 / L 209.23 / C 209.66 / V 145,070,184
- COIN 2026-08-25: O 176.00 / H 189.27 / L 174.73 / C 187.16 / V 10,565,300
- CIEN, DAC, DELL, F, HUBB의 Open 경계만 High/Low envelope로 정규화

DB 스키마 변경이나 Migration은 없다. 전환 직전 DB 백업은 `db/backups/drct_asset_before_yfinance_20260827_1040.sqlite3`에 보관한다.
