from __future__ import annotations

# Legacy compatibility wrapper.
# New standard client path:
#   backend.app.clients.kiwoom.kiwoom_rest_client.KiwoomRestClient

from backend.app.clients.kiwoom.kiwoom_models import KiwoomRestResponse
from backend.app.clients.kiwoom.kiwoom_rest_client import KiwoomRestClient

__all__ = ["KiwoomRestClient", "KiwoomRestResponse"]

