# Economic Briefing Plan (30-A)

## 목적
- 경제 유튜브 채널/재생목록과 수동 URL을 기반으로 분석 후보 영상을 관리한다.
- 영상 메타데이터/요약 결과를 저장하고 조회한다.

## 운영 방식
- 고정 source(채널/재생목록) + 수동 URL 하이브리드 운영
- 프론트는 백엔드 API만 호출

## 자막 저장 원칙
- 자막 전문(full transcript) DB 저장 금지
- 자막은 분석 시점 임시 처리만 허용

## DB 저장 데이터
- source 정보(channel/playlist)
- 영상 메타데이터(video_id, title, published_at, 상태 컬럼)
- 요약 결과(briefing_summaries)
- 주제별 아이템(briefing_topic_items)
- 테마 연결(briefing_theme_links)

## DB 비저장 데이터
- full transcript
- segment 단위 transcript 원문
- 장문 description 원문(필요 시 description_summary만)

## 후속 PoC
- transcript 임시 추출 파이프라인
- LLM chunk 요약/통합 요약
- 시장 테마/종목 자동 연결 보조

## 30-C transcript 임시 추출 PoC
- 목적:
1. 영상 자막 추출 가능 여부를 사전 확인
2. 자막 전문 비저장 원칙 유지

- 구현 원칙:
1. DB에는 `transcript_status/language/source`와 길이/청크 수 같은 메타만 저장
2. full transcript/segment json 저장 금지
3. API 응답도 full transcript 미포함

- transcript-check API:
1. `POST /economic-briefing/videos/{video_id}/transcript-check`
2. 성공 시 `available` + 언어/길이/chunk 수 저장
3. 실패 시 `unavailable` 또는 `failed` 저장

- chunk 분할:
1. 기본 `max_chars=4000`, `overlap_chars=300`
2. preview는 최대 200자만 응답

- 다음 단계(30-D):
1. chunk 기반 LLM 요약 실행
2. `briefing_summaries`, `briefing_topic_items` 저장
3. 테마/종목 언급 구조화 저장

## 30-D LLM chunk 요약 실행/저장
- 파이프라인:
1. transcript 임시 추출 (메모리)
2. chunk 분할
3. chunk 요약
4. 통합 요약/주제 추출
5. 요약 결과 저장

- 저장 정책:
1. transcript 전문 및 chunk 원문은 DB 저장 금지
2. `briefing_summaries`에는 `summary_type=full` 기준 upsert 저장
3. `briefing_topic_items`는 재분석 시 해당 영상 기존 항목 삭제 후 재생성

- API:
1. `POST /economic-briefing/videos/{video_id}/summarize`
2. `GET /economic-briefing/videos/{video_id}/summaries`

- 저장 결과:
1. 전체 요약
2. 핵심 포인트
3. 주제별 요약
4. 언급 테마/종목
5. 리스크 포인트
6. 시장 관찰 포인트(핵심 포인트에 병합)

- 실패 처리:
1. transcript 불가 또는 LLM 실패 시 `analysis_status=failed`
2. `error_message`에는 짧은 요약 오류만 저장
3. traceback/민감정보 저장 금지

- 보안 원칙:
1. API 응답에 transcript 전문 미포함
2. YouTube/LLM 관련 KEY 응답·로그 노출 금지

## 30-B-1 refresh-videos 실동작
- source playlist 동기화:
1. `POST /economic-briefing/sources/{source_id}/refresh-videos`
2. `playlistItems.list`로 video_id 목록 조회
3. `videos.list`로 제목/채널/게시일/길이/썸네일/description 요약 조회
4. `briefing_videos`에 `video_id` 기준 upsert

- upsert 정책:
1. 신규 영상은 `transcript_status=unknown`, `analysis_status=pending`
2. 기존 영상은 메타데이터만 갱신하고 transcript/analysis 상태는 유지
3. `briefing_sources.last_checked_at` 갱신

- 메타데이터 정리 규칙:
1. duration은 ISO8601(`PT..`)을 초 단위 정수로 변환
2. description은 full text 저장 금지, `description_summary` 최대 300자로 제한
3. thumbnail은 `high -> medium -> default` 우선순위 선택

- 보안/용량 원칙 유지:
1. YouTube API KEY는 `.env` 로드만 허용
2. API 응답/로그에 KEY 노출 금지
3. transcript 전문 비저장 유지

## 30-B-2 refresh-videos FK 오류 보강
- 원인:
1. `briefing_videos.source_id`가 고아(orphan) 값일 때 메타데이터 upsert 과정에서 FK 충돌 가능
2. 기존 `COALESCE(source_id, :source_id)` 방식은 고아 source_id를 안전하게 복구하지 못함

- 수정:
1. `repair_orphan_briefing_video_source_ids()` 추가
2. refresh 시작 전에 orphan source_id를 `NULL`로 정비
3. upsert 시 `source_id`를 명시적으로 결정:
   - 기존 source_id가 유효하면 유지
   - 기존 source_id가 NULL 또는 orphan이면 현재 refresh source_id로 보정
4. `COALESCE(source_id, :source_id)` 제거 후 `source_id=:resolved_source_id` 사용

- 예외 처리:
1. source 연결 이상 시 사용자 친화 메시지 반환
2. raw SQL/traceback/API key는 응답에 노출하지 않음

- 데이터 보존 원칙:
1. `briefing_videos` 행 삭제 없음
2. `briefing_summaries`, `briefing_topic_items` 삭제 없음
3. source soft delete 정책 유지

## 30-C-2 transcript-check 안정화 (youtube-transcript-api 1.1.1)
- 실패 원인:
1. 자막 조회 순서가 list 계열 우선이어서 fetch 가능한 영상도 실패로 종료될 수 있었음
2. chunk 분할 루프가 일부 입력에서 역진행하여 `MemoryError`가 발생할 수 있었음

- 개선:
1. 1순위: `api.fetch(video_id, languages=['ko','en'])`
2. 2순위: `YouTubeTranscriptApi.get_transcript(...)`
3. 3순위: `list_transcripts/list` 진단 fallback
4. FetchedTranscript / list[dict] 정규화 공통 처리
5. chunk 분할 포인터 역진행 방지 로직 추가

- 응답/저장 정책:
1. `transcript_status=available` 저장 기준: text_length>0, chunk_count>0
2. 실패 시 시도 내역(`attempts`)과 축약 오류만 반환
3. full transcript는 DB/API 모두 비저장 유지

## 30-D-1 LM Studio empty content 대응
- 원인:
1. 일부 reasoning 계열 모델에서 `message.content` 없이 `reasoning_content`만 생성 후 `finish_reason=length`로 종료 가능
2. chunk 입력이 길거나 프롬프트가 복잡하면 최종 JSON 미출력 확률 증가

- 대응:
1. chunk 프롬프트 단순화 및 JSON-only 지시 강화
2. chunk 요약 `max_tokens=1500`, 재시도 `max_tokens=2000`
3. 통합 요약 `max_tokens=3000`, 재시도 `max_tokens=3500`
4. LLM 요약용 chunk 별도 분할(`max_chars=2500`, `overlap_chars=150`)
5. empty content 시 짧은 재시도 프롬프트 적용
6. chunk 단위 실패 fallback 적용(전체 중단 방지)

- 안전 원칙:
1. reasoning_content는 저장/노출 금지
2. 디버그 로그는 reasoning 본문 대신 길이만 출력
3. transcript/chunk 원문 비저장 유지

- 모델 안내:
1. reasoning 계열에서 empty content가 반복되면 instruct 계열 모델(qwen/llama/gemma instruct) 권장

## 30-D-2 source 물리 삭제/thumbnail 비저장 정책
- source 삭제 정책:
1. `DELETE /economic-briefing/sources/{source_id}` 시 soft delete 대신 물리 삭제
2. 삭제 전 `briefing_videos.source_id`를 `NULL`로 먼저 해제
3. `briefing_videos`, `briefing_summaries`, `briefing_topic_items`, `briefing_theme_links`는 삭제하지 않음
4. 삭제된 source 영상은 미분류(`source_id IS NULL`)로 조회 가능

- thumbnail 정책:
1. YouTube metadata refresh/playlist refresh/manual refresh 모두 `thumbnail_url` 저장 금지
2. 신규/갱신 upsert에서 `thumbnail_url`은 항상 `NULL`
3. 기존 `thumbnail_url`도 일괄 `NULL` 정비
4. 프론트 영상 목록의 썸네일 컬럼 제거

## 30-D-2-1 UI/UX 정리
- 탭 구조:
1. 채널/재생목록 관리
2. 영상 목록
3. 분석 결과
4. 수동 URL 분석 탭은 관리 탭으로 통합

- 영상 목록 UX:
1. source 선택 필터 추가(전체 / 수동·미분류 / source별)
2. 게시일 표시를 `yyyy-mm-dd`로 통일
3. 컬럼 정리: 썸네일/언어/chunk 수/자막길이 제거
4. 상태 한글화: 자막상태·분석상태 코드값을 화면에서 한글 표기
5. 관리 버튼 소형화 및 가로 배치
6. 요약 실행은 추정 progress(0→90% 점진, 완료 시 100%) 표시
7. 요약 중 중복 클릭 방지(disabled)
8. 요약보기는 모달로 표시(요약/핵심포인트/주제/테마/종목/리스크)

- 향후 개선:
1. background summary job
2. 실제 progress polling
3. chunk 병렬 처리
4. 더 빠른 instruct 모델 적용

## 30-D-2-2 요약보기 UX/등록 구조 통합
- 탭 구조 단순화:
1. `분석 결과` 탭 제거
2. `채널/재생목록 관리`, `영상 목록` 2개 탭 유지

- 요약보기 UX:
1. 탭 전환 없이 영상 목록 아래 인라인 상세 패널로 표시
2. 같은 영상 재클릭 시 접기
3. 다른 영상 선택 시 내용 교체
4. 요약/핵심포인트/주제/테마/종목/리스크만 노출(원문/추론 미노출)

- URL 등록 UX:
1. `YouTube URL 등록` 카드로 통합
2. 등록 유형 선택: `재생목록` / `단일 영상`
3. 프론트에서 유형에 따라 기존 API 분기 호출
   - 재생목록: `POST /economic-briefing/sources`
   - 단일영상: `POST /economic-briefing/videos/manual`
4. playlist URL과 video URL의 역할 안내 문구 분리

- 기존 API 정책:
1. backend API는 기존 경로 유지
2. 통합 URL 등록 API는 후속 검토

## 30-D-3 LLM 요약 속도 최적화
- 병목 원인:
1. chunk 수가 많아 LLM 호출 횟수가 증가
2. chunk 프롬프트가 과도하게 길면 응답 지연/재시도 증가
3. 이미 요약된 영상의 재실행으로 불필요한 처리 시간 소모

- 전용 설정:
1. `ECONOMIC_BRIEFING_CHUNK_MAX_CHARS=4000`
2. `ECONOMIC_BRIEFING_CHUNK_OVERLAP_CHARS=50`
3. `ECONOMIC_BRIEFING_CHUNK_MAX_TOKENS=700`
4. `ECONOMIC_BRIEFING_CHUNK_RETRY_MAX_TOKENS=1000`
5. `ECONOMIC_BRIEFING_OVERALL_MAX_TOKENS=1800`
6. `ECONOMIC_BRIEFING_SKIP_IF_SUMMARIZED=true`

- 프롬프트 최적화:
1. chunk 단계는 `summary/themes/stocks/risks`의 경량 JSON만 생성
2. overall 단계에서만 `overall_summary/key_points/topics/theme_mentions/stock_mentions/risk_points` 최종 구조 생성

- 재요약 방지:
1. `force=false` 기본
2. `summary_has_content=true`면 기존 요약을 재사용하고 안내 메시지 반환
3. 재요약은 사용자 확인 후 `force=true`로만 수행

- 처리 시간 메타:
1. `briefing_summaries.elapsed_seconds`
2. `briefing_summaries.chunk_count`
3. 상세 패널에서 모델/처리시간/chunk 수 표시

- 타이밍 로그:
1. transcript fetch, chunk split, chunk별 요약, overall 요약, DB 저장, total 단계 elapsed 로그 출력
2. 원문 자막/프롬프트/API KEY는 로그 비노출

- 원칙 유지:
1. transcript 전문/chunk 원문 DB 비저장
2. `briefing_transcripts` 테이블 미생성 유지
3. `thumbnail_url` 신규 저장 금지 유지
