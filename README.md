# OpenElo Player Market

A trading platform for positions in professional footballers, priced by a public bonding curve and paying dividends pegged to an open, reproducible rating (OpenElo). Design: [docs/Spec.md](docs/Spec.md).

| Path | Contents |
|---|---|
| `docs/` | Spec, architecture decision records (`docs/adr/`) |
| `services/` | Backend microservices (see [ADR-0001](docs/adr/0001-service-decomposition.md)) |
| `infra/` | Docker Compose stack, migrations, CI |
| `frontend/` | Client (later) |
| `research/` | Offline rating-validation tool (Python, never deployed) |
