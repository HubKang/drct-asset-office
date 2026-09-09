from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from unittest.mock import Mock

from backend.app.services.drct_insight_service import DrctInsightService


class _Db:
    def __init__(self) -> None:
        self.bind = object()

    def get_bind(self) -> object:
        return self.bind


def test_today_reuses_short_cache_and_force_refreshes(monkeypatch) -> None:
    db = _Db()
    service = DrctInsightService(db)  # type: ignore[arg-type]
    calls = 0

    def build(_self):
        nonlocal calls
        calls += 1
        return {"version": calls}

    monkeypatch.setattr(DrctInsightService, "_build_today", build)
    DrctInsightService.invalidate_today_cache(db.bind)

    first = service.today()
    cached = service.today()
    refreshed = service.today(force_refresh=True)

    assert first is cached
    assert refreshed == {"version": 2}
    assert calls == 2
    DrctInsightService.invalidate_today_cache(db.bind)


def test_today_coalesces_concurrent_rebuilds(monkeypatch) -> None:
    db = _Db()
    started = Event()
    release = Event()
    count_lock = Lock()
    calls = 0

    def build(_self):
        nonlocal calls
        with count_lock:
            calls += 1
        started.set()
        assert release.wait(timeout=2)
        return {"snapshot": "shared"}

    monkeypatch.setattr(DrctInsightService, "_build_today", build)
    DrctInsightService.invalidate_today_cache(db.bind)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(DrctInsightService(db).today)  # type: ignore[arg-type]
        assert started.wait(timeout=1)
        second = executor.submit(DrctInsightService(db).today)  # type: ignore[arg-type]
        release.set()
        assert first.result(timeout=2) is second.result(timeout=2)

    assert calls == 1
    DrctInsightService.invalidate_today_cache(db.bind)


def test_capture_reuses_today_result_without_rebuilding(monkeypatch) -> None:
    service = DrctInsightService(_Db())  # type: ignore[arg-type]
    row = Mock(focus_candidate=True, final_candidate=False)
    result = Mock(market_mode="POST_MARKET", analysis_date="2026-09-08", stocks=[row])
    captured = Mock()
    result.model_copy.return_value = captured
    today = Mock(return_value=result)
    persist = Mock()
    publish = Mock()
    monkeypatch.setattr(service, "today", today)
    monkeypatch.setattr(service, "_persist_candidate_rows", persist)
    monkeypatch.setattr(service, "_publish_today_cache", publish)

    assert service.capture_today_candidates() is captured
    today.assert_called_once_with()
    persist.assert_called_once_with("2026-09-08", [row])
    result.model_copy.assert_called_once_with(update={"evaluation_captured": True})
    publish.assert_called_once_with(captured)
