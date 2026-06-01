from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import DB_PATH, PROJECT_ROOT
from backend.app.core.database import SessionLocal
from backend.app.repositories.stock_price_repository import StockPriceRepository


TARGET_SOURCE = "kiwoom_rest"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _make_backup() -> Path:
    backup_dir = PROJECT_ROOT / "db" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"drct_asset_before_fix_change_rate_{_now_stamp()}.sqlite3"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def _mismatch_count(session) -> int:
    sql = text(
        """
        WITH calculated AS (
            SELECT
                p.id,
                p.change_rate AS saved_change_rate,
                LAG(p.close_price) OVER (
                    PARTITION BY p.stock_id
                    ORDER BY p.trade_date
                ) AS prev_close,
                ROUND(
                    (p.close_price - LAG(p.close_price) OVER (
                        PARTITION BY p.stock_id
                        ORDER BY p.trade_date
                    )) * 100.0
                    / LAG(p.close_price) OVER (
                        PARTITION BY p.stock_id
                        ORDER BY p.trade_date
                    ),
                    2
                ) AS calculated_change_rate
            FROM stock_daily_prices p
            WHERE p.source = :source
        )
        SELECT COUNT(*)
        FROM calculated
        WHERE prev_close IS NOT NULL
          AND (
              saved_change_rate IS NULL
              OR calculated_change_rate IS NULL
              OR ABS(saved_change_rate - calculated_change_rate) >= 0.01
          )
        """
    )
    return int(session.execute(sql, {"source": TARGET_SOURCE}).scalar() or 0)


def _sample_rows(session, limit: int = 10) -> list[dict]:
    sql = text(
        """
        WITH calculated AS (
            SELECT
                p.id,
                s.stock_code,
                s.stock_name,
                p.trade_date,
                p.close_price,
                p.change_rate AS saved_change_rate,
                LAG(p.close_price) OVER (
                    PARTITION BY p.stock_id
                    ORDER BY p.trade_date
                ) AS prev_close,
                ROUND(
                    (p.close_price - LAG(p.close_price) OVER (
                        PARTITION BY p.stock_id
                        ORDER BY p.trade_date
                    )) * 100.0
                    / LAG(p.close_price) OVER (
                        PARTITION BY p.stock_id
                        ORDER BY p.trade_date
                    ),
                    2
                ) AS calculated_change_rate,
                p.source
            FROM stock_daily_prices p
            JOIN stocks s
                ON s.id = p.stock_id
            WHERE p.source = :source
        )
        SELECT
            stock_code,
            stock_name,
            trade_date,
            close_price,
            saved_change_rate,
            calculated_change_rate,
            ROUND(saved_change_rate - calculated_change_rate, 2) AS diff,
            source
        FROM calculated
        WHERE prev_close IS NOT NULL
        ORDER BY ABS(COALESCE(saved_change_rate, 0) - COALESCE(calculated_change_rate, 0)) DESC, stock_code ASC, trade_date DESC
        LIMIT :limit
        """
    )
    rows = session.execute(sql, {"source": TARGET_SOURCE, "limit": limit}).mappings().all()
    return [dict(r) for r in rows]


def _verify_specific_rows(session) -> list[dict]:
    sql = text(
        """
        WITH x AS (
            SELECT
                s.stock_code,
                s.stock_name,
                p.trade_date,
                p.close_price,
                p.change_rate,
                LAG(p.close_price) OVER (PARTITION BY p.stock_id ORDER BY p.trade_date) AS prev_close
            FROM stock_daily_prices p
            JOIN stocks s ON s.id = p.stock_id
            WHERE p.source = :source
              AND s.stock_code IN ('097230', '010170')
        )
        SELECT
            stock_code,
            stock_name,
            trade_date,
            close_price,
            prev_close,
            change_rate,
            ROUND(((close_price - prev_close) * 100.0 / prev_close), 2) AS recalculated
        FROM x
        WHERE trade_date = '2026-06-01'
        ORDER BY stock_code
        """
    )
    rows = session.execute(sql, {"source": TARGET_SOURCE}).mappings().all()
    return [dict(r) for r in rows]


def main() -> None:
    backup_path = _make_backup()
    print(f"[backup] path={backup_path}")
    print(f"[backup] size_bytes={backup_path.stat().st_size}")
    print(f"[target] source={TARGET_SOURCE}")

    with SessionLocal() as session:
        repo = StockPriceRepository(session)
        total_rows = int(
            session.execute(
                text("SELECT COUNT(*) FROM stock_daily_prices WHERE source = :source"),
                {"source": TARGET_SOURCE},
            ).scalar()
            or 0
        )
        print(f"[before] total_target_rows={total_rows}")
        print(f"[before] mismatch_rows={_mismatch_count(session)}")
        before_samples = _sample_rows(session, limit=10)
        print("[before] sample_top10_diff")
        for row in before_samples:
            print(row)

        stock_ids = repo.list_distinct_stock_ids_by_source(TARGET_SOURCE)
        updated_total = 0
        null_total = 0
        error_count = 0
        for stock_id in stock_ids:
            try:
                result = repo.recalculate_change_rate_for_stock(stock_id=stock_id, source=TARGET_SOURCE, digits=2)
                updated_total += int(result["updated_count"])
                null_total += int(result["null_count"])
            except Exception:
                error_count += 1

        print(f"[after] updated_rows={updated_total}")
        print(f"[after] null_rows={null_total}")
        print(f"[after] error_stock_count={error_count}")
        print(f"[after] mismatch_rows={_mismatch_count(session)}")
        after_samples = _sample_rows(session, limit=10)
        print("[after] sample_top10_diff")
        for row in after_samples:
            print(row)
        print("[verify] 2026-06-01 target stocks")
        for row in _verify_specific_rows(session):
            print(row)


if __name__ == "__main__":
    main()
