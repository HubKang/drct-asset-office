# DrCT에셋 DESIGN.md

## 1\. 디자인 방향 개요

DrCT에셋의 디자인 언어는 **AI 투자 분석 콘솔**을 중심으로 한다. 화면은 단순한 주식 관리 도구가 아니라, 뉴스·공시·가격·재무·수급 데이터를 수집하고 이를 투자 판단 근거로 정리하는 **1인 투자회사 운영실**처럼 보여야 한다.

전체 분위기는 어두운 바이올렛 계열의 분석 콘솔을 기본으로 하되, 투자자가 빠르게 주목해야 할 키워드와 액션에는 라임색 하이라이트를 제한적으로 사용한다. 다크 화면은 리서치, 분석, 요약, 분류, AI 처리 상태처럼 집중이 필요한 영역에 사용하고, 라이트 화면은 규칙 관리, 데이터 목록, 설정, 입력 폼처럼 정보 비교와 수정이 많은 영역에 사용한다.

핵심 인상은 다음과 같다.

* 어두운 투자 분석실 같은 배경
* 라임색으로 강조되는 핵심 투자 키워드
* 카드형 데이터 블록
* 콘솔 로그처럼 정돈된 상태 정보
* 복잡한 데이터를 빠르게 판단할 수 있는 명확한 위계
* 최종 투자 판단을 자동화하지 않고, 판단 근거를 정리해 주는 보조 시스템의 신뢰감

DrCT에셋은 “화려한 증권앱”이 아니라 “AI 리서치 조직을 운영하는 투자자의 내부 관제실”처럼 보여야 한다.

\---

## 2\. 핵심 디자인 원칙

### 2.1 두 가지 화면 성격을 분리한다

DrCT에셋의 화면은 크게 두 가지 성격으로 나눈다.

1. **다크 분석 화면**

   * 대시보드
   * AI 요약
   * 뉴스·공시 분석
   * 종목 리서치
   * GPT 자문용 근거 패키지
   * 리스크 검토
2. **라이트 관리 화면**

   * 종목 관리
   * 관심종목 관리
   * 분류 규칙 관리
   * 수집 이력 관리
   * 설정 화면
   * 데이터 입력·수정 화면

다크 화면과 라이트 화면을 애매하게 섞지 않는다. 한 화면의 주요 성격을 먼저 정하고, 해당 성격에 맞는 배경·카드·버튼 체계를 유지한다.

### 2.2 라임색은 희소하게 사용한다

라임색은 DrCT에셋의 핵심 강조색이다. 하지만 버튼, 본문, 배경에 남발하지 않는다.

라임색은 다음 용도로만 사용한다.

* 핵심 키워드 하이라이트
* 중요한 상태 배지
* 선택된 메뉴 또는 활성 탭의 포인트
* 페이지당 가장 중요한 지표 1\~2개
* 투자 이벤트 유형 강조

라임색은 “많이 보이는 색”이 아니라 “보이면 바로 집중되는 색”이어야 한다.

### 2.3 자동 판단보다 근거 정리를 강조한다

DrCT에셋은 매수·매도 결정을 자동으로 단정하지 않는다. 화면에서도 “매수 추천”, “강력 매도”처럼 오해될 수 있는 표현은 피한다.

대신 다음 표현 체계를 사용한다.

* 투자 판단 근거
* 긍정 요인
* 부정 요인
* 확인 필요 사항
* 리스크 신호
* 중요도 점수
* 뉴스 감성
* 공시 이벤트 유형
* GPT 검토용 근거

디자인도 이러한 철학을 반영해야 한다. 버튼과 카드 문구는 과장된 투자 앱 느낌보다, 리서치 노트와 리스크 관리 도구의 신중함을 가져야 한다.

\---

## 3\. 컬러 시스템

### 3.1 브랜드 컬러

|토큰|색상|용도|
|-|-:|-|
|`--color-primary`|`#150f23`|가장 깊은 배경, 주요 버튼, 강한 카드 배경|
|`--color-ink-deep`|`#1f1633`|다크 기본 배경, 라이트 화면의 본문 텍스트|
|`--color-surface-dark`|`#1f1633`|대시보드·분석 화면 배경|
|`--color-surface-night`|`#150f23`|다크 카드, 코드 블록, 강조 패널|
|`--color-accent-lime`|`#c2ef4e`|핵심 키워드, 활성 상태, 중요 배지|
|`--color-accent-pink`|`#fa7faa`|보조 강조, 경고성 시각 포인트, 차트 포인트|
|`--color-accent-violet`|`#6a5fc1`|링크, 보조 버튼, 탭 강조|
|`--color-accent-violet-deep`|`#422082`|보라색 강조 카드, 선택 영역|
|`--color-accent-violet-mid`|`#79628c`|태그 칩, 보조 배지|

### 3.2 표면 색상

|토큰|색상|용도|
|-|-:|-|
|`--color-canvas-dark`|`#1f1633`|분석 중심 페이지 배경|
|`--color-canvas-light`|`#ffffff`|관리·입력·목록 페이지 배경|
|`--color-surface-soft`|`#f7f7fb`|라이트 화면의 보조 패널|
|`--color-hairline-violet`|`#362d59`|다크 카드 경계선|
|`--color-hairline-cloud`|`#e5e7eb`|라이트 카드·테이블 경계선|
|`--color-hairline-cool`|`#cfcfdb`|입력 필드 경계선|

### 3.3 텍스트 색상

|토큰|색상|용도|
|-|-:|-|
|`--color-on-primary`|`#ffffff`|다크 배경의 기본 텍스트|
|`--color-ink`|`#1f1633`|라이트 배경의 기본 텍스트|
|`--color-muted-dark`|`rgba(255,255,255,0.72)`|다크 화면 보조 텍스트|
|`--color-faint-dark`|`rgba(255,255,255,0.18)`|다크 화면 비활성 영역|
|`--color-muted-light`|`#6b7280`|라이트 화면 보조 텍스트|
|`--color-danger`|`#ef4444`|오류, 실패, 고위험|
|`--color-warning`|`#f59e0b`|주의, 중간 위험|
|`--color-success`|`#22c55e`|성공, 완료, 긍정 상태|
|`--color-focus-ring`|`rgba(59,130,246,0.5)`|키보드 포커스 링|

\---

## 4\. 타이포그래피

### 4.1 기본 폰트

* 화면 전체 기본 폰트는 `Rubik`, `Pretendard`, `Noto Sans KR`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif` 순서로 사용한다.
* 숫자, 코드, 로그, API 경로, SQL은 `Monaco`, `Menlo`, `Consolas`, `monospace`를 사용한다.
* 한글 화면에서는 가독성을 위해 `Pretendard` 또는 `Noto Sans KR`이 자연스럽게 적용되도록 한다.

### 4.2 크기 체계

|토큰|크기|굵기|행간|용도|
|-|-:|-:|-:|-|
|`--font-display-hero`|64px|700|1.15|메인 대시보드 히어로 문구|
|`--font-display-large`|48px|700|1.15|주요 섹션 제목|
|`--font-heading-xl`|30px|600|1.25|페이지 제목|
|`--font-heading-lg`|27px|600|1.25|큰 카드 제목|
|`--font-heading-md`|24px|600|1.3|섹션 제목|
|`--font-heading-sm`|20px|600|1.3|카드 제목|
|`--font-body-lg`|16px|400|2.0|설명형 문단|
|`--font-body-md`|16px|500|1.5|기본 UI 텍스트|
|`--font-caption`|14px|400|1.43|보조 설명, 도움말|
|`--font-button`|14px|700|1.14|버튼 라벨|
|`--font-micro`|10px|600|1.8|상태 배지, 작은 라벨|
|`--font-code`|14px|400|1.5|로그, SQL, API 경로|

### 4.3 문구 스타일

* 버튼 라벨은 가능하면 짧고 명령형으로 쓴다.

  * 예: `요약 실행`, `재분류`, `규칙 추가`, `근거 패키지 생성`
* 상태 배지는 명사형으로 쓴다.

  * 예: `수집 완료`, `요약 실패`, `위험 높음`, `확인 필요`
* 투자 판단을 단정하지 않는다.

  * 피해야 할 표현: `매수 확정`, `급등 보장`, `반드시 매도`
  * 권장 표현: `긍정 요인`, `주의 요인`, `검토 필요`, `리스크 신호`

\---

## 5\. 레이아웃 시스템

### 5.1 간격

|토큰|값|용도|
|-|-:|-|
|`--space-xxs`|2px|미세 간격|
|`--space-xs`|4px|배지 내부 간격|
|`--space-sm`|8px|작은 요소 간격|
|`--space-md`|12px|입력 필드, 버튼 내부 간격|
|`--space-lg`|16px|카드 내부 기본 간격|
|`--space-xl`|24px|섹션 내부 간격|
|`--space-xxl`|32px|큰 카드 패딩|
|`--space-section`|96px|주요 화면 밴드 간격|

### 5.2 화면 구조

기본 앱 구조는 다음을 권장한다.

```text
App Shell
├─ Top Header
│  ├─ 프로젝트 로고 / 현재 모듈명
│  ├─ 주요 메뉴
│  └─ 실행 버튼 / 상태 표시
├─ Main Layout
│  ├─ Left Sidebar
│  │  ├─ Dashboard
│  │  ├─ Stocks
│  │  ├─ Watchlist
│  │  ├─ News
│  │  ├─ Disclosures
│  │  ├─ Collection Runs
│  │  ├─ Classification Rules
│  │  └─ GPT Evidence Package
│  └─ Content Area
│     ├─ Page Header
│     ├─ Filter / Action Bar
│     ├─ Cards or Table
│     └─ Detail Panel
└─ Optional Footer / Status Bar
```

### 5.3 반응형 기준

|구간|너비|처리|
|-|-:|-|
|Wide|1440px 이상|좌측 메뉴와 대시보드 카드 4열 유지|
|Desktop|1152px 이상|기본 3\~4열 카드 구성|
|Laptop|992px 이상|2\~3열 카드 구성|
|Tablet|768px 이상|좌측 메뉴 축소, 카드 2열|
|Mobile|640px 이하|사이드바 접힘, 카드 1열, 테이블은 가로 스크롤|

\---

## 6\. 컴포넌트 규칙

### 6.1 버튼

#### Primary Button

가장 중요한 실행 버튼에만 사용한다.

* 라이트 화면: 배경 `#150f23`, 글자 `#ffffff`
* 다크 화면: 배경 `#ffffff`, 글자 `#1f1633`
* 높이 최소 44px
* 둥근 정도 8px
* 텍스트는 짧고 명확하게 작성

권장 사용 예:

* `뉴스 수집`
* `공시 수집`
* `AI 요약 실행`
* `재분류 실행`
* `규칙 저장`
* `근거 패키지 생성`

#### Secondary Button

보조 액션에 사용한다.

* 배경은 투명 또는 약한 보라색
* 테두리 사용 가능
* Primary Button보다 시각적으로 약해야 한다.

권장 사용 예:

* `초기화`
* `필터 열기`
* `상세 보기`
* `테스트 실행`

#### Danger Button

삭제, 비활성화, 초기화처럼 되돌리기 어려운 작업에 사용한다.

* 배경 또는 테두리에 위험 색상 사용
* 라벨은 구체적으로 작성

  * `규칙 비활성화`
  * `수집 이력 삭제`

\---

### 6.2 카드

#### Dark Analysis Card

분석 요약, 리스크, AI 처리 결과에 사용한다.

* 배경: `#150f23` 또는 `#1f1633`
* 테두리: `#362d59`
* 제목: 흰색
* 보조 설명: 흰색 72% 투명도
* 라임색은 카드 안에서 최대 1개 핵심 요소에만 사용

사용 예:

* 오늘의 주요 뉴스 요약
* 공시 리스크 요약
* GPT 검토용 근거 카드
* AI 요약 처리 상태

#### Light Management Card

관리·입력·목록 화면에 사용한다.

* 배경: `#ffffff`
* 테두리: `#e5e7eb`
* 제목: `#1f1633`
* 보조 설명: `#6b7280`

사용 예:

* 종목 기본 정보
* 분류 규칙 등록 폼
* 수집 이력 테이블
* 관심종목 설정

\---

### 6.3 테이블

테이블은 라이트 화면을 기본으로 한다. 데이터 비교가 많은 화면에서는 다크 테이블보다 라이트 테이블이 적합하다.

공통 규칙:

* 헤더는 14px, 600 굵기
* 본문은 14\~15px
* 행 높이 최소 44px
* 중요 상태는 배지로 표현
* 긴 요약문은 2줄 말줄임 처리 후 상세 패널에서 전체 표시
* 테이블의 첫 번째 열은 식별 정보, 마지막 열은 액션 버튼으로 둔다.

권장 컬럼 예:

뉴스 목록:

```text
종목 | 제목 | 출처 | 감성 | 중요도 | 태그 | AI 요약 | 처리일시 | 액션
```

공시 목록:

```text
종목 | 공시명 | 이벤트 유형 | 리스크 | 중요도 | 태그 | AI 요약 | 공시일 | 액션
```

분류 규칙:

```text
그룹 | 대상 | 규칙명 | 키워드 | 출력 필드 | 출력값 | 점수 | 우선순위 | 활성 | 액션
```

\---

### 6.4 배지와 태그

배지는 작은 정보 판단을 빠르게 도와야 한다.

#### 감성 배지

|값|표현|색상 방향|
|-|-|-|
|positive|긍정|초록 계열|
|neutral|중립|회색 계열|
|negative|부정|분홍·빨강 계열|

#### 리스크 배지

|값|표현|색상 방향|
|-|-|-|
|high|위험 높음|빨강 계열|
|medium|주의 필요|주황 계열|
|low|위험 낮음|초록 또는 보라 계열|
|unknown|미분류|회색 계열|

#### 이벤트 유형 배지

공시 이벤트 유형은 다음 기준을 기본으로 한다.

|이벤트 유형|기본 리스크|
|-|-|
|소송|high|
|자본|medium|
|투자|medium|
|지분변동|medium|
|계약|low|
|실적|low|
|배당|low|
|자사주|low|
|주주총회|low|
|기타|unknown|

\---

## 7\. 주요 화면별 디자인 가이드

### 7.1 대시보드

대시보드는 다크 분석 화면으로 구성한다.

구성:

1. 상단 히어로 영역

   * “오늘의 투자 판단 근거를 정리합니다”와 같은 문구
   * 핵심 단어 1개를 라임 칩으로 강조
   * 오늘 수집된 뉴스·공시·AI 요약 건수 표시
2. 요약 카드 영역

   * 관심종목 수
   * 오늘 수집 뉴스 수
   * 오늘 수집 공시 수
   * AI 요약 성공/실패 수
3. 주요 신호 영역

   * 중요도 높은 뉴스
   * 고위험 공시
   * 확인 필요 항목
4. 실행 영역

   * `뉴스 수집`
   * `공시 수집`
   * `AI 요약 실행`
   * `재분류 실행`

### 7.2 뉴스 화면

뉴스 화면은 분석 성격이 강하므로 다크 또는 혼합형으로 구성할 수 있다.

권장 구조:

* 상단: 다크 페이지 헤더
* 본문: 라이트 테이블
* 우측 또는 하단: AI 요약 상세 패널

중요도 점수는 숫자만 보여주지 말고 색상·배지와 함께 표현한다.

예:

```text
78 / 중요
50 / 보통
25 / 낮음
```

### 7.3 공시 화면

공시 화면은 리스크 판단이 중요하므로 이벤트 유형과 리스크 수준이 먼저 보이게 한다.

우선순위:

1. 종목
2. 공시명
3. 이벤트 유형
4. 리스크 수준
5. 중요도 점수
6. AI 요약
7. 원문 링크 또는 상세 보기

`unknown`은 단순 회색으로 방치하지 말고 `미분류` 또는 `규칙 확인 필요`로 표시한다.

### 7.4 분류 규칙 관리 화면

분류 규칙 관리 화면은 라이트 관리 화면으로 구성한다.

필수 구성:

* 규칙 목록 테이블
* 규칙 등록 버튼
* 규칙 수정 모달 또는 상세 패널
* 비활성화 버튼
* 활성/비활성 필터
* 대상 필터: 뉴스 / 공시 / 통합
* 출력 필드 필터: tag / sentiment / score / event\_type / risk\_level

폼 필드:

* rule\_group
* target\_type
* rule\_name
* keywords
* output\_field
* output\_value
* score\_delta
* priority
* is\_active
* description

입력 도움말:

* keywords는 쉼표로 구분한다.
* priority가 높을수록 먼저 적용한다.
* score\_delta는 중요도 점수 보정값이다.
* is\_active가 false이면 분류에 사용하지 않는다.

### 7.5 GPT 자문용 근거 패키지 화면

11단계에서 개발할 화면이다.

다크 분석 화면으로 구성한다.

구성:

1. 종목 선택
2. 기간 선택
3. 포함 데이터 선택

   * 뉴스
   * 공시
   * 가격
   * 재무
   * 수급
4. 근거 패키지 미리보기
5. GPT에 붙여넣기 좋은 Markdown 생성
6. 리스크 확인 체크리스트

이 화면의 목적은 자동 투자 판단이 아니라, GPT Plus에 전달할 고품질 근거 자료를 만드는 것이다.

\---

## 8\. CSS 토큰 예시

프로젝트 전역 CSS에 다음 토큰을 우선 적용한다.

```css
:root {
  --color-primary: #150f23;
  --color-ink-deep: #1f1633;
  --color-canvas-dark: #1f1633;
  --color-surface-night: #150f23;
  --color-canvas-light: #ffffff;
  --color-surface-soft: #f7f7fb;

  --color-accent-lime: #c2ef4e;
  --color-accent-pink: #fa7faa;
  --color-accent-violet: #6a5fc1;
  --color-accent-violet-deep: #422082;
  --color-accent-violet-mid: #79628c;

  --color-on-primary: #ffffff;
  --color-ink: #1f1633;
  --color-muted-dark: rgba(255, 255, 255, 0.72);
  --color-faint-dark: rgba(255, 255, 255, 0.18);
  --color-muted-light: #6b7280;

  --color-hairline-violet: #362d59;
  --color-hairline-cloud: #e5e7eb;
  --color-hairline-cool: #cfcfdb;

  --color-danger: #ef4444;
  --color-warning: #f59e0b;
  --color-success: #22c55e;
  --color-focus-ring: rgba(59, 130, 246, 0.5);

  --space-xxs: 2px;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-xxl: 32px;
  --space-section: 96px;

  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --radius-xl: 12px;
  --radius-xxl: 18px;
  --radius-full: 9999px;
}
```

\---

## 9\. 공통 CSS 클래스 예시

```css
body {
  margin: 0;
  font-family: Rubik, Pretendard, 'Noto Sans KR', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--color-ink);
  background: var(--color-canvas-light);
}

.app-shell {
  min-height: 100vh;
  background: var(--color-canvas-light);
}

.app-shell.dark {
  color: var(--color-on-primary);
  background: radial-gradient(circle at top left, rgba(194, 239, 78, 0.08), transparent 28%),
              radial-gradient(circle at top right, rgba(250, 127, 170, 0.08), transparent 24%),
              var(--color-canvas-dark);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-xl);
  margin-bottom: var(--space-xl);
}

.page-title {
  margin: 0;
  font-size: 30px;
  line-height: 1.25;
  font-weight: 600;
}

.page-description {
  margin: var(--space-sm) 0 0;
  color: var(--color-muted-light);
  font-size: 14px;
  line-height: 1.5;
}

.dark .page-description {
  color: var(--color-muted-dark);
}

.keyword-chip {
  display: inline-block;
  padding: 0 var(--space-md);
  border-radius: var(--radius-xs);
  color: var(--color-ink-deep);
  background: var(--color-accent-lime);
}

.btn {
  min-height: 44px;
  border: 0;
  border-radius: var(--radius-md);
  padding: var(--space-md) var(--space-lg);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.14;
  letter-spacing: 0.2px;
  cursor: pointer;
}

.btn-primary {
  color: var(--color-on-primary);
  background: var(--color-primary);
}

.dark .btn-primary,
.btn-inverted {
  color: var(--color-ink-deep);
  background: var(--color-on-primary);
}

.btn-secondary {
  color: var(--color-ink-deep);
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline-cloud);
}

.dark .btn-secondary {
  color: var(--color-on-primary);
  background: var(--color-faint-dark);
  border: 1px solid var(--color-hairline-violet);
}

.card {
  border-radius: var(--radius-xl);
  padding: var(--space-xl);
  background: var(--color-canvas-light);
  border: 1px solid var(--color-hairline-cloud);
}

.card-dark {
  color: var(--color-on-primary);
  background: var(--color-surface-night);
  border: 1px solid var(--color-hairline-violet);
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  min-height: 24px;
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.badge-risk-high {
  color: #ffffff;
  background: var(--color-danger);
}

.badge-risk-medium {
  color: #1f1633;
  background: var(--color-warning);
}

.badge-risk-low {
  color: #1f1633;
  background: var(--color-accent-lime);
}

.badge-risk-unknown {
  color: #6b7280;
  background: #f3f4f6;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.data-table th,
.data-table td {
  min-height: 44px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-hairline-cloud);
  text-align: left;
  vertical-align: middle;
}

.data-table th {
  color: var(--color-muted-light);
  font-weight: 600;
  background: var(--color-surface-soft);
}
```

\---

## 10\. 화면 적용 우선순위

DrCT에셋 전체 화면에 한 번에 무리하게 적용하지 말고, 다음 순서로 적용한다.

### 1순위: 전역 디자인 토큰

* `src/index.css`, `src/App.css`, `src/styles/\*` 중 실제 전역 CSS 파일 확인
* 컬러 토큰 추가
* 간격 토큰 추가
* radius 토큰 추가
* 기본 body 폰트와 배경 수정

### 2순위: App Shell

* 상단 헤더 정리
* 좌측 메뉴 정리
* 현재 선택 메뉴 강조
* 다크/라이트 화면 구분 가능하도록 layout class 부여

### 3순위: 주요 목록 화면

* 뉴스 목록
* 공시 목록
* 수집 이력
* 분류 규칙 목록

테이블, 배지, 액션 버튼을 먼저 통일한다.

### 4순위: AI 분석 화면

* 뉴스 AI 요약
* 공시 AI 요약
* 통합 source-items 요약
* 재분류 실행 결과

AI 처리 상태, 성공/실패 메시지, 요약 카드의 디자인을 통일한다.

### 5순위: 분류 규칙 관리 화면

* 등록 폼
* 수정 폼
* 비활성화 버튼
* 필터 영역
* 규칙 테스트 영역

### 6순위: GPT 자문용 근거 패키지 화면

11단계 개발 시 이 디자인 체계를 기준으로 신규 화면을 설계한다.

\---

## 11\. 하지 말아야 할 것

* 라임색을 일반 본문 텍스트에 사용하지 않는다.
* 투자 판단을 단정하는 문구를 사용하지 않는다.
* 다크 화면에 과한 그림자 효과를 넣지 않는다.
* 카드 안에 너무 많은 색상의 배지를 섞지 않는다.
* 한 화면에서 Primary Button을 여러 개 남발하지 않는다.
* 테이블의 모든 컬럼에 강한 색을 넣지 않는다.
* `unknown` 상태를 방치하지 말고, 사용자가 조치할 수 있는 문구를 제공한다.
* 로컬 LLM 결과를 최종 투자 판단처럼 보이게 하지 않는다.

\---

## 12\. Codex 적용 지시 기준

Codex는 이 문서를 기준으로 다음 작업을 수행한다.

1. 프로젝트 루트에 `DESIGN.md`를 생성한다.
2. 기존 프론트엔드 구조를 확인한다.
3. 전역 CSS 파일 위치를 확인한다.
4. 디자인 토큰을 전역 CSS에 추가한다.
5. 공통 버튼, 카드, 배지, 테이블 스타일을 정리한다.
6. 기존 기능 동작을 변경하지 않고 className 중심으로 스타일만 개선한다.
7. 뉴스 수집, 공시 수집, AI 요약, 재분류 API 호출 로직은 건드리지 않는다.
8. 분류 규칙 관리 화면은 라이트 관리 화면으로 정리한다.
9. 대시보드와 AI 분석 화면은 다크 분석 화면으로 정리한다.
10. 변경 후 다음 명령으로 확인한다.

```bash
npm install
npm run lint
npm run build
npm run dev
```

백엔드 기능은 수정하지 않는다. 단, 프론트엔드에서 상태값을 보여주는 라벨 문구와 배지 스타일은 개선할 수 있다.

\---

## 13\. 적용 완료 기준

디자인 적용이 완료되었다고 판단하려면 다음 조건을 만족해야 한다.

* 모든 주요 화면에서 버튼 스타일이 통일되어 있다.
* 뉴스와 공시의 감성·중요도·리스크 배지가 일관되게 표시된다.
* `unknown` 상태가 `미분류` 또는 `규칙 확인 필요`로 표현된다.
* 분류 규칙 관리 화면에서 테이블과 폼이 라이트 관리 화면 기준으로 정돈되어 있다.
* 대시보드 또는 AI 분석 화면은 다크 분석 화면 기준으로 정돈되어 있다.
* 라임색은 핵심 강조에만 제한적으로 사용된다.
* 기존 API 호출과 데이터 흐름은 깨지지 않는다.
* `npm run build`가 성공한다.

