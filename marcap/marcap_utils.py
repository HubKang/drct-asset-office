from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests


DATA_ROOT = Path(__file__).resolve().parent / "data"
RAW_BASE_URL = "https://raw.githubusercontent.com/FinanceData/marcap/master/data"


def _ensure_parquet(year: int) -> Path:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    parquet_path = DATA_ROOT / f"marcap-{year}.parquet"
    if parquet_path.exists():
        return parquet_path

    url = f"{RAW_BASE_URL}/marcap-{year}.parquet"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    parquet_path.write_bytes(response.content)
    return parquet_path


def _load_year_frame(year: int) -> pd.DataFrame:
    path = _ensure_parquet(year)
    frame = pd.read_parquet(path)
    if "Date" not in frame.columns:
        raise ValueError("marcap parquet is missing required 'Date' column")
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.normalize()
    return frame


def marcap_latest_available_date(year: int) -> pd.Timestamp | None:
    frame = _load_year_frame(year)
    if frame.empty:
        return None
    latest = frame["Date"].max()
    if pd.isna(latest):
        return None
    return pd.Timestamp(latest).normalize()


def marcap_data(start, end=None, code: str | None = None):
    start_dt = pd.to_datetime(start).normalize()
    end_dt = start_dt if end is None else pd.to_datetime(end).normalize()

    frames = []
    for year in range(start_dt.year, end_dt.year + 1):
        frames.append(_load_year_frame(year))

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)
    merged = merged[(start_dt <= merged["Date"]) & (merged["Date"] <= end_dt)]
    merged = merged.sort_values(["Date", "Rank"], ascending=[True, True])

    if code:
        merged = merged[merged["Code"] == code]

    merged = merged[merged["Volume"] > 0]
    merged = merged.set_index("Date")
    return merged
