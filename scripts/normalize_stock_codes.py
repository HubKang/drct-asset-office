from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import SessionLocal
from backend.app.schemas.stock_schema import StockCodeNormalizeRequest
from backend.app.services.stock_service import StockService


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize KR stock codes (A123456 -> 123456).")
    parser.add_argument("--apply", action="store_true", help="Apply updates. Default is dry-run.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = StockService(db)
        result = service.normalize_stock_codes(StockCodeNormalizeRequest(dry_run=not args.apply))
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(
            f"[{mode}] target_count={result.target_count} updated_count={result.updated_count} "
            f"conflicts={result.duplicate_conflict_count}"
        )
        for item in result.items:
            print(f"{item.status:>11} | {item.old_code} -> {item.new_code} | {item.stock_name} (id={item.stock_id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
