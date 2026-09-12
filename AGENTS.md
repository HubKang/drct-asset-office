# Repository development rules

## Change scope and verification

- For UI-only changes, reuse of existing functionality, and similarly scoped modifications that do not introduce a new screen, new business logic, or a functional improvement, apply the requested change directly and skip token-intensive broad regression testing.
- Keep verification proportional to the change: perform only lightweight, targeted checks when useful, unless the user explicitly requests broader testing or the change reveals a concrete higher-risk impact.

## Data retention

- Do not persist raw provider responses, validation samples, simulation samples, chart series, or other reproducible detail unless a feature has an explicit future read path and retention period.
- Keep validation and simulation detail transient. Persist only aggregate metrics required for operation, history, comparison, or audit.
- Store JSON through an explicit durable-field allow-list; never persist an entire API or simulation response by default.
- Do not expose internal JSON blobs from list/detail APIs. Return explicit aggregate response fields.
- Back up the database before compacting existing JSON and verify integrity before reclaiming SQLite file space.
- Follow `docs/data-retention-policy.md` for project-specific details.
