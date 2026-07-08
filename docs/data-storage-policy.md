# Data Storage Policy

## Normalized data first

Do not store unused source payloads in application tables after the values needed by the product are mapped into explicit columns.

Rules:
- Add or reuse typed columns for values used by screens, scoring, search, or reports.
- Do not persist raw API response blobs only for debugging.
- If a source field is not used by the product, leave it out of the database.
- If a field becomes necessary later, add a column or a purpose-built table at that time.
- Temporary diagnostics should use logs or one-off probes, not long-lived business tables.

For investor flow collection, `stock_investor_flows.raw_json` is retained only for schema compatibility and should remain `NULL` for new writes.
