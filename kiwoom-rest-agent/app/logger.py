from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def mask_sensitive(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def sanitize_payload(payload: dict | None) -> dict:
    if payload is None:
        return {}
    sensitive_keys = {"appkey", "secretkey", "token", "authorization", "access_token"}
    out: dict = {}
    for k, v in payload.items():
        if k.lower() in sensitive_keys and isinstance(v, str):
            out[k] = mask_sensitive(v)
        else:
            out[k] = v
    return out


def get_logger(name: str = "kiwoom_rest_agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = Path(__file__).resolve().parents[1] / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logfile = log_dir / f"kiwoom_rest_agent_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
