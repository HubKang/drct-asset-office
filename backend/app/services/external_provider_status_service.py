from __future__ import annotations

from dataclasses import dataclass

from backend.app.core import config
from backend.app.core.config import now_kst


@dataclass(frozen=True)
class ProviderKeySpec:
    provider: str
    display_name: str
    values: tuple[str, ...]
    configured_message: str
    missing_message: str


class ExternalProviderStatusService:
    PROVIDERS = (
        ProviderKeySpec(
            provider="KIWOOM_REST",
            display_name="\ud0a4\uc6c0 REST API",
            values=(config.KIWOOM_REST_APP_KEY, config.KIWOOM_REST_SECRET_KEY, config.KIWOOM_REST_ACCESS_TOKEN),
            configured_message="API credential is configured. Endpoint mapping and token freshness may still be required.",
            missing_message="KIWOOM_REST_APP_KEY, KIWOOM_REST_SECRET_KEY \ub610\ub294 ACCESS_TOKEN \uc124\uc815\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
        ),
        ProviderKeySpec(
            provider="KRX_OPEN_API",
            display_name="KRX Open API",
            values=(config.KRX_OPEN_API_KEY,),
            configured_message="API key is configured. Service-specific approval and endpoint mapping may still be required.",
            missing_message="KRX_OPEN_API_KEY \ub610\ub294 KRX_OPEN_API_AUTH_KEY \uc124\uc815\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
        ),
        ProviderKeySpec(
            provider="DATA_GO_KR",
            display_name="\uacf5\uacf5\ub370\uc774\ud130\ud3ec\ud138",
            values=(config.DATA_GO_KR_SERVICE_KEY, config.DATA_GO_KR_DECODING_KEY, config.DATA_GO_KR_ENCODING_KEY),
            configured_message="API key is configured. Select a service endpoint before enabling collection.",
            missing_message="DATA_GO_KR_SERVICE_KEY \ub610\ub294 decoding/encoding key \uc124\uc815\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
        ),
        ProviderKeySpec(
            provider="BOK_ECOS",
            display_name="BOK ECOS",
            values=(config.BOK_ECOS_API_KEY,),
            configured_message="ECOS key is configured. 59-B\uc5d0\uc11c \ud1b5\uacc4\ucf54\ub4dc \ub9e4\ud551 \ud6c4 \uc218\uc9d1\uc744 \ud65c\uc131\ud654\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
            missing_message="BOK_ECOS_API_KEY \uc124\uc815\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
        ),
        ProviderKeySpec(
            provider="KOSIS",
            display_name="KOSIS",
            values=(config.KOSIS_API_KEY,),
            configured_message="KOSIS key is configured. Dataset mapping is still required.",
            missing_message="KOSIS_API_KEY \uc124\uc815\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
        ),
        ProviderKeySpec(
            provider="FRED",
            display_name="FRED",
            values=(config.FRED_API_KEY,),
            configured_message="FRED key is configured. US market indicators can be tested and collected.",
            missing_message="FRED_API_KEY \uc124\uc815\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
        ),
    )

    @staticmethod
    def _first_value(values: tuple[str, ...]) -> str:
        return next((value.strip() for value in values if value and value.strip()), "")

    @staticmethod
    def mask_key(value: str | None) -> str | None:
        key = (value or "").strip()
        if not key:
            return None
        if len(key) <= 8:
            return f"{key[:2]}{'*' * max(2, len(key) - 2)}"
        return f"{key[:4]}{'*' * max(8, len(key) - 8)}{key[-4:]}"

    def list_statuses(self) -> list[dict[str, object]]:
        checked_at = now_kst()
        items: list[dict[str, object]] = []
        for spec in self.PROVIDERS:
            key_value = self._first_value(spec.values)
            configured = bool(key_value)
            status = "WAITING_SERVICE_MAPPING" if configured else "MISSING_KEY"
            if configured and spec.provider in {"KIWOOM_REST", "KRX_OPEN_API", "DATA_GO_KR", "BOK_ECOS", "KOSIS", "FRED"}:
                status = "CONFIGURED"
            items.append(
                {
                    "provider": spec.provider,
                    "display_name": spec.display_name,
                    "configured": configured,
                    "masked_key": self.mask_key(key_value),
                    "status": status,
                    "message": spec.configured_message if configured else spec.missing_message,
                    "last_checked_at": checked_at,
                }
            )
        return items
