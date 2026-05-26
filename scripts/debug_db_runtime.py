from __future__ import annotations

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import DATABASE_URL, DB_PATH, PROJECT_ROOT as CONFIG_PROJECT_ROOT
from backend.app.core.database import engine


def main() -> None:
    print(f"cwd={os.getcwd()}")
    print(f"PROJECT_ROOT={CONFIG_PROJECT_ROOT}")
    print(f"DB_PATH={DB_PATH}")
    print(f"DATABASE_URL={DATABASE_URL}")
    print(f"engine.url={engine.url}")
    print(f"db_exists={Path(DB_PATH).exists()}")

    with engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA database_list").fetchall()
        print(f"PRAGMA database_list={rows}")
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS __sa_write_test__(id INTEGER PRIMARY KEY, memo TEXT)"
        )
        conn.exec_driver_sql("INSERT INTO __sa_write_test__(memo) VALUES ('sqlalchemy_write_test')")
        conn.commit()
        print("sqlalchemy write ok")


if __name__ == "__main__":
    main()
