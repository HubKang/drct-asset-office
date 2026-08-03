from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app


@pytest.fixture
def isolated_api_client() -> Generator[TestClient, None, None]:
    """Run mutating API tests against a disposable in-memory database."""

    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    test_session_local = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        class_=Session,
    )

    def override_get_db() -> Generator[Session, None, None]:
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()
