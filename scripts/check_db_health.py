from __future__ import annotations

import argparse
import sqlite3
import sys
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import DATABASE_URL, DB_PATH
from backend.app.core.database import engine

EXIT_OK = 0
EXIT_INTEGRITY_FAILED = 1
EXIT_DB_PATH_FAILED = 2
EXIT_WRITE_FAILED = 3
EXIT_SQLALCHEMY_FAILED = 4
EXIT_UNEXPECTED = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DrCT DB health check")
    parser.add_argument("--verbose", action="store_true", help="print verbose diagnostics")
    parser.add_argument("--skip-write", action="store_true", help="skip sqlite3/sqlalchemy write tests")
    return parser.parse_args()


def resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError(f"sqlite only: {database_url}")

    parsed = urlparse(database_url)
    raw_path = unquote(parsed.path or "")
    if raw_path.startswith("/./"):
        raw_path = raw_path[1:]
    if raw_path.startswith("/") and len(raw_path) >= 3 and raw_path[2] == ":":
        raw_path = raw_path[1:]

    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = (PROJECT_ROOT / db_path).resolve()
    return db_path


def _format_exception(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def _bool(v: bool) -> str:
    return "OK" if v else "FAIL"


def main() -> int:
    args = parse_args()
    failures: list[tuple[int, str]] = []
    warnings: list[str] = []
    db_path = resolve_sqlite_path(DATABASE_URL)
    db_dir = db_path.parent
    db_exists = db_path.exists()
    db_size = db_path.stat().st_size if db_exists else -1
    db_readonly = (not os.access(db_path, os.W_OK)) if db_exists else True

    folder_write_ok = False
    folder_write_error = ""
    folder_probe = db_dir / "__db_health_folder_write_test__.tmp"
    try:
        folder_probe.write_text("db-health", encoding="utf-8")
        folder_write_ok = True
    except Exception as exc:
        folder_write_error = _format_exception(exc)
        failures.append((EXIT_WRITE_FAILED, f"DB folder write failed: {folder_write_error}"))
    finally:
        try:
            if folder_probe.exists():
                folder_probe.unlink()
        except Exception as exc:
            warnings.append(f"folder probe cleanup failed: {_format_exception(exc)}")

    sqlite_write_ok = False
    sqlite_write_error = ""
    sqlalchemy_write_ok = False
    sqlalchemy_write_error = ""
    db_list_sqlite3: list[tuple] = []
    db_list_sa: list[tuple] = []
    journal_mode = ""
    synchronous = ""
    busy_timeout = ""
    integrity = ""

    if not db_exists:
        failures.append((EXIT_DB_PATH_FAILED, "DB file does not exist"))
    else:
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            db_list_sqlite3 = cur.execute("PRAGMA database_list").fetchall()
            journal_mode = str((cur.execute("PRAGMA journal_mode").fetchone() or [""])[0])
            synchronous = str((cur.execute("PRAGMA synchronous").fetchone() or [""])[0])
            busy_timeout = str((cur.execute("PRAGMA busy_timeout").fetchone() or [""])[0])
            integrity = str((cur.execute("PRAGMA integrity_check").fetchone() or [""])[0])

            if integrity.lower() != "ok":
                failures.append((EXIT_INTEGRITY_FAILED, f"integrity_check failed: {integrity}"))

            if not args.skip_write:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS __db_health_write_test__(
                        id INTEGER PRIMARY KEY,
                        test_type TEXT,
                        created_at TEXT
                    )
                    """
                )
                cur.execute(
                    "INSERT INTO __db_health_write_test__(test_type, created_at) VALUES (?, datetime('now'))",
                    ("sqlite3",),
                )
                cur.execute("DELETE FROM __db_health_write_test__ WHERE test_type = ?", ("sqlite3",))
                conn.commit()
                sqlite_write_ok = True
            conn.close()
        except Exception as exc:
            sqlite_write_error = _format_exception(exc)
            if "readonly" in str(exc).lower() or "permission" in str(exc).lower():
                failures.append((EXIT_WRITE_FAILED, f"sqlite3 write failed: {sqlite_write_error}"))
            else:
                failures.append((EXIT_UNEXPECTED, f"sqlite3 check failed: {sqlite_write_error}"))

    try:
        with engine.connect() as sa_conn:
            db_list_sa = sa_conn.exec_driver_sql("PRAGMA database_list").fetchall()
            if not args.skip_write:
                sa_conn.exec_driver_sql(
                    """
                    CREATE TABLE IF NOT EXISTS __db_health_write_test__(
                        id INTEGER PRIMARY KEY,
                        test_type TEXT,
                        created_at TEXT
                    )
                    """
                )
                sa_conn.exec_driver_sql(
                    "INSERT INTO __db_health_write_test__(test_type, created_at) VALUES ('sqlalchemy', datetime('now'))"
                )
                sa_conn.exec_driver_sql(
                    "DELETE FROM __db_health_write_test__ WHERE test_type = 'sqlalchemy'"
                )
                sa_conn.commit()
                sqlalchemy_write_ok = True
    except Exception as exc:
        sqlalchemy_write_error = _format_exception(exc)
        if "readonly" in str(exc).lower() or "permission" in str(exc).lower():
            failures.append((EXIT_WRITE_FAILED, f"sqlalchemy write failed: {sqlalchemy_write_error}"))
        else:
            failures.append((EXIT_SQLALCHEMY_FAILED, f"sqlalchemy connection/write failed: {sqlalchemy_write_error}"))

    wal = Path(f"{db_path}-wal")
    shm = Path(f"{db_path}-shm")
    journal = Path(f"{db_path}-journal")

    status_ok = len(failures) == 0
    print("[DB Health] OK" if status_ok else "[DB Health] FAILED")
    print(f"- cwd: {os.getcwd()}")
    print(f"- PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"- DB_PATH(config): {DB_PATH}")
    print(f"- DB_PATH(resolved): {db_path}")
    print(f"- DATABASE_URL: {DATABASE_URL}")
    print(f"- engine.url: {engine.url}")
    print(f"- DB file exists: {_bool(db_exists)}")
    print(f"- DB file size: {db_size}")
    print(f"- DB file readonly: {'YES' if db_readonly else 'NO'}")
    print(f"- DB folder exists: {_bool(db_dir.exists())}")
    print(f"- DB folder write: {_bool(folder_write_ok)}")
    if folder_write_error:
        print(f"- DB folder write error: {folder_write_error}")
    print(f"- PRAGMA database_list(sqlite3): {db_list_sqlite3}")
    print(f"- PRAGMA database_list(sqlalchemy): {db_list_sa}")
    print(f"- PRAGMA journal_mode: {journal_mode}")
    print(f"- PRAGMA synchronous: {synchronous}")
    print(f"- PRAGMA busy_timeout: {busy_timeout}")
    print(f"- WAL exists: {wal.exists()}")
    print(f"- SHM exists: {shm.exists()}")
    print(f"- JOURNAL exists: {journal.exists()}")
    print(f"- integrity_check: {integrity or 'N/A'}")
    print(f"- sqlite3 write: {'SKIPPED' if args.skip_write else ('OK' if sqlite_write_ok else 'FAIL')}")
    if sqlite_write_error:
        print(f"- sqlite3 write error: {sqlite_write_error}")
    print(f"- sqlalchemy write: {'SKIPPED' if args.skip_write else ('OK' if sqlalchemy_write_ok else 'FAIL')}")
    if sqlalchemy_write_error:
        print(f"- sqlalchemy write error: {sqlalchemy_write_error}")

    if args.verbose:
        for table in [
            "stocks",
            "watchlist",
            "news_items",
            "disclosures",
            "collection_runs",
            "classification_rules",
            "telegram_sources",
            "telegram_items",
            "telegram_daily_summaries",
            "trade_methods",
            "trade_journals",
            "trade_journal_images",
        ]:
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                conn.close()
                print(f"- table_count[{table}]: {count}")
            except Exception as exc:
                print(f"- table_count[{table}]: ERROR {_format_exception(exc)}")

    if warnings:
        print("- warnings:")
        for w in warnings:
            print(f"  - {w}")

    if failures:
        print("- 원인 후보:")
        dedup = []
        for _code, msg in failures:
            if msg not in dedup:
                dedup.append(msg)
        for msg in dedup:
            print(f"  - {msg}")
        print("- 확인 필요:")
        print("  1. 현재 셸/프로세스 권한(쓰기 가능 여부)")
        print("  2. DB 파일/폴더 ACL 및 잠금 프로세스")
        print("  3. DATABASE_URL과 PRAGMA database_list 경로 일치 여부")
        print("  4. WAL/SHM 파일 생성 가능 여부")

    if status_ok:
        return EXIT_OK
    # highest-priority failure code
    codes = [code for code, _ in failures]
    if EXIT_DB_PATH_FAILED in codes:
        return EXIT_DB_PATH_FAILED
    if EXIT_INTEGRITY_FAILED in codes:
        return EXIT_INTEGRITY_FAILED
    if EXIT_WRITE_FAILED in codes:
        return EXIT_WRITE_FAILED
    if EXIT_SQLALCHEMY_FAILED in codes:
        return EXIT_SQLALCHEMY_FAILED
    return EXIT_UNEXPECTED


if __name__ == "__main__":
    raise SystemExit(main())
