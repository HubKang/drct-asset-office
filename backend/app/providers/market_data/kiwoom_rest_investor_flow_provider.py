from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.app.clients.kiwoom import KiwoomApiError, KiwoomRestClient
from backend.app.utils.stock_code import normalize_stock_code


class KiwoomInvestorFlowNotConfigured(RuntimeError):
    pass


@dataclass
class KiwoomInvestorFlowRow:
    flow_date: str
    individual_buy_qty: int | None = None
    individual_sell_qty: int | None = None
    individual_net_qty: int | None = None
    individual_buy_amount: int | None = None
    individual_sell_amount: int | None = None
    individual_net_amount: int | None = None
    foreign_buy_qty: int | None = None
    foreign_sell_qty: int | None = None
    foreign_net_qty: int | None = None
    foreign_buy_amount: int | None = None
    foreign_sell_amount: int | None = None
    foreign_net_amount: int | None = None
    foreign_holding_qty: int | None = None
    foreign_holding_ratio: float | None = None
    institution_buy_qty: int | None = None
    institution_sell_qty: int | None = None
    institution_net_qty: int | None = None
    institution_buy_amount: int | None = None
    institution_sell_amount: int | None = None
    institution_net_amount: int | None = None
    financial_investment_net_qty: int | None = None
    insurance_net_qty: int | None = None
    investment_trust_net_qty: int | None = None
    bank_net_qty: int | None = None
    other_finance_net_qty: int | None = None
    pension_fund_net_qty: int | None = None
    private_fund_net_qty: int | None = None
    other_corporation_net_qty: int | None = None
    program_buy_qty: int | None = None
    program_sell_qty: int | None = None
    program_net_qty: int | None = None
    program_buy_amount: int | None = None
    program_sell_amount: int | None = None
    program_net_amount: int | None = None
    program_arbitrage_net_qty: int | None = None
    program_non_arbitrage_net_qty: int | None = None
    raw_json: dict[str, Any] = field(default_factory=dict)


class KiwoomRestInvestorFlowProvider:
    INVESTOR_API_ID = 'ka10059'
    INVESTOR_PATH = '/api/dostk/stkinfo'
    PROGRAM_API_ID = 'ka90013'
    PROGRAM_PATH = '/api/dostk/mrkcond'
    FOREIGN_HOLDING_API_ID = 'ka10008'
    FOREIGN_HOLDING_PATH = '/api/dostk/frgnistt'

    def __init__(self) -> None:
        self.client = KiwoomRestClient()

    def get_investor_flows(
        self,
        *,
        stock_code: str,
        start_date: str,
        end_date: str,
        max_rows: int = 160,
        include_trade_breakdown: bool = True,
        include_foreign_holding: bool = True,
    ) -> dict[str, Any]:
        normalized = normalize_stock_code(stock_code)
        base_date = end_date.replace('-', '')
        errors: dict[str, str] = {}

        def safe_fetch(*, name: str, path: str, api_id: str, body: dict[str, Any], row_key: str) -> dict[str, Any]:
            try:
                return self._fetch_pages(
                    path=path, api_id=api_id, body=body, row_key=row_key, max_rows=max_rows
                )
            except Exception as exc:  # noqa: BLE001
                errors[name] = str(exc)[:500]
                return {'rows': [], 'pages': 0}

        trade_sides = (('net', '0'), ('buy', '1'), ('sell', '2')) if include_trade_breakdown else (('net', '0'),)
        qty_payloads = {
            side: safe_fetch(
                name=f'ka10059_qty_{side}',
                path=self.INVESTOR_PATH,
                api_id=self.INVESTOR_API_ID,
                body={'stk_cd': normalized, 'dt': base_date, 'amt_qty_tp': '2', 'trde_tp': code, 'unit_tp': '1'},
                row_key='stk_invsr_orgn',
            )
            for side, code in trade_sides
        }
        amount_payloads = {
            side: safe_fetch(
                name=f'ka10059_amount_{side}',
                path=self.INVESTOR_PATH,
                api_id=self.INVESTOR_API_ID,
                body={'stk_cd': normalized, 'dt': base_date, 'amt_qty_tp': '1', 'trde_tp': code, 'unit_tp': '1'},
                row_key='stk_invsr_orgn',
            )
            for side, code in trade_sides
        }
        program_payloads = safe_fetch(
            name='ka90013',
            path=self.PROGRAM_PATH,
            api_id=self.PROGRAM_API_ID,
            body={'stk_cd': normalized, 'dt': base_date},
            row_key='stk_daly_prm_trde_trnsn',
        )
        holding_error: str | None = None
        holding_payloads = {'rows': [], 'pages': 0}
        if include_foreign_holding:
            try:
                holding_payloads = self._fetch_pages(
                    path=self.FOREIGN_HOLDING_PATH,
                    api_id=self.FOREIGN_HOLDING_API_ID,
                    body={'stk_cd': normalized},
                    row_key='stk_frgnr',
                    max_rows=max_rows,
                )
            except Exception as exc:  # noqa: BLE001
                holding_error = str(exc)

        rows_by_date: dict[str, KiwoomInvestorFlowRow] = {}
        for side, payloads in qty_payloads.items():
            for raw in payloads['rows']:
                row = self._map_ka10059_qty_row(raw, trade_side=side)
                if row:
                    rows_by_date[row.flow_date] = self._merge_row(rows_by_date.get(row.flow_date), row)
        for side, payloads in amount_payloads.items():
            for raw in payloads['rows']:
                row = self._map_ka10059_amount_row(raw, trade_side=side)
                if row:
                    rows_by_date[row.flow_date] = self._merge_row(rows_by_date.get(row.flow_date), row)
        for raw in program_payloads['rows']:
            row = self._map_ka90013_row(raw)
            if row:
                rows_by_date[row.flow_date] = self._merge_row(rows_by_date.get(row.flow_date), row)
        for raw in holding_payloads['rows']:
            row = self._map_ka10008_holding_row(raw)
            if row:
                rows_by_date[row.flow_date] = self._merge_row(rows_by_date.get(row.flow_date), row)

        rows = [rows_by_date[k] for k in sorted(rows_by_date.keys())]
        source_methods = ['kiwoom_rest_ka10059', 'kiwoom_rest_ka90013']
        if include_foreign_holding:
            source_methods.append('kiwoom_rest_ka10008')
        return {
            'provider': 'kiwoom_rest',
            'stock_code': stock_code,
            'normalized_stock_code': normalized,
            'source_methods': source_methods,
            'investor_api_id': self.INVESTOR_API_ID,
            'investor_path': self.INVESTOR_PATH,
            'program_api_id': self.PROGRAM_API_ID,
            'program_path': self.PROGRAM_PATH,
            'ka10059_qty_count': sum(len(payload['rows']) for payload in qty_payloads.values()),
            'ka10059_amount_count': sum(len(payload['rows']) for payload in amount_payloads.values()),
            'ka90013_count': len(program_payloads['rows']),
            'ka10008_count': len(holding_payloads['rows']),
            'ka10008_error': holding_error,
            'collection_errors': errors,
            'items': [row.__dict__ for row in rows],
        }

    def _fetch_pages(self, *, path: str, api_id: str, body: dict[str, Any], row_key: str, max_rows: int, max_pages: int = 6) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        cont_yn: str | None = None
        next_key: str | None = None
        pages = 0
        while pages < max_pages:
            response = self.client.post_json(path, api_id=api_id, body=body, cont_yn=cont_yn, next_key=next_key)
            payload = response.json_body
            code = str(payload.get('return_code', '')).strip()
            if code not in ('', '0', '000000'):
                raise KiwoomApiError(code=code, message=str(payload.get('return_msg') or f'{api_id} investor flow request failed'))
            rows.extend(self._extract_rows(payload, row_key))
            pages += 1
            if len(rows) >= max_rows:
                break
            if response.cont_yn != 'Y' or not response.next_key:
                break
            cont_yn = 'Y'
            next_key = response.next_key
        return {'rows': rows, 'pages': pages}

    @staticmethod
    def _extract_rows(payload: dict[str, Any], row_key: str) -> list[dict[str, Any]]:
        candidate = payload.get(row_key)
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]
        return []

    @classmethod
    def _map_ka10059_qty_row(cls, row: dict[str, Any], trade_side: str = 'net') -> KiwoomInvestorFlowRow | None:
        flow_date = cls._normalize_date(cls._get_first_str(row, ('dt', 'date', 'trd_dt', 'base_dt', 'trade_date')))
        if not flow_date:
            return None
        values = {
            'individual': cls._get_first_int(row, ('ind_invsr', 'individual_investor', 'individual_net_qty')),
            'foreign': cls._get_first_int(row, ('frgnr_invsr', 'foreign_net_qty', 'for_netprps')),
            'institution': cls._get_first_int(row, ('orgn', 'institution_net_qty', 'orgn_netprps')),
        }
        base = KiwoomInvestorFlowRow(flow_date=flow_date)
        if trade_side == 'net':
            base.financial_investment_net_qty = cls._get_first_int(row, ('fnnc_invt', 'financial_investment_net_qty'))
            base.insurance_net_qty = cls._get_first_int(row, ('insrnc', 'insurance_net_qty'))
            base.investment_trust_net_qty = cls._get_first_int(row, ('invtrt', 'investment_trust_net_qty'))
            base.bank_net_qty = cls._get_first_int(row, ('bank', 'bank_net_qty'))
            base.other_finance_net_qty = cls._get_first_int(row, ('etc_fnnc', 'other_finance_net_qty'))
            base.pension_fund_net_qty = cls._get_first_int(row, ('penfnd_etc', 'pension_fund_net_qty'))
            base.private_fund_net_qty = cls._get_first_int(row, ('samo_fund', 'private_fund_net_qty'))
            base.other_corporation_net_qty = cls._get_first_int(row, ('etc_corp', 'other_corporation_net_qty'))
        for subject, value in values.items():
            setattr(base, f'{subject}_{trade_side}_qty', value)
        return base

    @classmethod
    def _map_ka10059_amount_row(cls, row: dict[str, Any], trade_side: str = 'net') -> KiwoomInvestorFlowRow | None:
        flow_date = cls._normalize_date(cls._get_first_str(row, ('dt', 'date', 'trd_dt', 'base_dt', 'trade_date')))
        if not flow_date:
            return None
        base = KiwoomInvestorFlowRow(flow_date=flow_date)
        for subject, keys in (
            ('individual', ('ind_invsr', 'individual_investor', 'individual_net_amount')),
            ('foreign', ('frgnr_invsr', 'foreign_net_amount')),
            ('institution', ('orgn', 'institution_net_amount')),
        ):
            setattr(base, f'{subject}_{trade_side}_amount', cls._get_first_amount(row, keys))
        return base

    @classmethod
    def _map_ka90013_row(cls, row: dict[str, Any]) -> KiwoomInvestorFlowRow | None:
        flow_date = cls._normalize_date(cls._get_first_str(row, ('dt', 'date', 'trd_dt', 'base_dt', 'trade_date')))
        if not flow_date:
            return None
        buy_qty = cls._get_first_int(row, ('prm_buy_qty', 'program_buy_qty'))
        sell_qty = cls._get_first_int(row, ('prm_sell_qty', 'program_sell_qty'))
        net_qty = cls._get_first_int(row, ('prm_netprps_qty', 'program_net_qty'))
        buy_amount = cls._get_first_amount(row, ('prm_buy_amt', 'program_buy_amount'))
        sell_amount = cls._get_first_amount(row, ('prm_sell_amt', 'program_sell_amount'))
        net_amount = cls._get_first_amount(row, ('prm_netprps_amt', 'program_net_amount'))
        return KiwoomInvestorFlowRow(
            flow_date=flow_date,
            program_buy_qty=buy_qty,
            program_sell_qty=sell_qty,
            program_net_qty=net_qty if net_qty is not None else cls._diff_optional(buy_qty, sell_qty),
            program_buy_amount=buy_amount,
            program_sell_amount=sell_amount,
            program_net_amount=net_amount if net_amount is not None else cls._diff_optional(buy_amount, sell_amount),
        )

    @classmethod
    def _map_ka10008_holding_row(cls, row: dict[str, Any]) -> KiwoomInvestorFlowRow | None:
        flow_date = cls._normalize_date(cls._get_first_str(row, ('dt', 'date', 'trd_dt', 'base_dt', 'trade_date')))
        if not flow_date:
            return None
        return KiwoomInvestorFlowRow(
            flow_date=flow_date,
            foreign_holding_qty=cls._get_first_int(row, ('poss_stkcnt', 'foreign_holding_qty')),
            foreign_holding_ratio=cls._get_first_float(row, ('wght', 'limit_exh_rt', 'foreign_holding_ratio')),
        )

    @staticmethod
    def _merge_row(base: KiwoomInvestorFlowRow | None, extra: KiwoomInvestorFlowRow) -> KiwoomInvestorFlowRow:
        if base is None:
            return extra
        for key, value in extra.__dict__.items():
            if key in {'flow_date', 'raw_json'}:
                continue
            if value is not None:
                setattr(base, key, value)
        return base

    @staticmethod
    def _diff_optional(buy: int | None, sell: int | None) -> int | None:
        if buy is None or sell is None:
            return None
        return buy - sell

    @staticmethod
    def _get_first_str(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            if key in row and row[key] is not None:
                value = str(row[key]).strip()
                if value:
                    return value
        return None

    @classmethod
    def _get_first_int(cls, row: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        for key in keys:
            if key in row:
                value = cls._to_int(row.get(key))
                if value is not None:
                    return value
        return None

    @classmethod
    def _get_first_amount(cls, row: dict[str, Any], keys: tuple[str, ...]) -> int | None:
        value = cls._get_first_int(row, keys)
        return None if value is None else value * 1_000_000

    @classmethod
    def _get_first_float(cls, row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            if key in row:
                value = cls._to_float(row.get(key))
                if value is not None:
                    return value
        return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        raw = str(value).replace(',', '').strip()
        if not raw:
            return None
        while raw.startswith('++') or raw.startswith('--'):
            raw = raw[1:]
        raw = raw.replace('+', '')
        try:
            return int(float(raw))
        except Exception:
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        raw = str(value).replace(',', '').replace('%', '').strip()
        if not raw:
            return None
        while raw.startswith('++') or raw.startswith('--'):
            raw = raw[1:]
        raw = raw.replace('+', '')
        try:
            return float(raw)
        except Exception:
            return None

    @staticmethod
    def _normalize_date(value: str | None) -> str | None:
        if not value:
            return None
        raw = value.strip().replace('-', '').replace('/', '').replace('.', '')
        if len(raw) != 8 or not raw.isdigit():
            return None
        try:
            return datetime.strptime(raw, '%Y%m%d').date().isoformat()
        except ValueError:
            return None
