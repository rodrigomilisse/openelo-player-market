# ADR-0001: Service decomposition and the money-core boundary

- **Status**: Accepted
- **Date**: 2026-10-01

## Context

OpenElo Player Market is being built partly as a learning project, so it uses mainstream, industry-standard technology and patterns (Spring Boot, PostgreSQL, Kafka, OAuth2/OIDC). It avoids niche scaling infrastructure. The aim is a system that can scale as an open, well-understood design, not one tuned for extreme scale.

The current focus is the systems and security engineering of the backend. The rating engine (OpenElo) is mocked behind an interface. The real formula is validated separately by the offline tool in `research/`.

The domain has two very different kinds of state:

1. **Money state**: wallet balances, share supply per player (which sets the bonding-curve price), trades and fees. A single mint changes all of these at once, and they must never disagree.
2. **Everything else**: football reference data, match ingestion, rating computation, dividend calculation and audit. These can tolerate seconds of propagation delay.

## Decision

### 1. Microservices, with service boundaries drawn along consistency boundaries

A service owns its data, and **anything that must change atomically lives inside one service and one database transaction.**

| Service | Owns | Notes |
|---|---|---|
| `market-service` | Ledger, wallets, bonding-curve pricing, trading (mint/redeem, later P2P) | The money core. One PostgreSQL database. Internally a modular monolith (`ledger`, `pricing`, `trading` packages with enforced one-way dependencies). |
| `rating-service` | Catalog (players, teams, competitions, matches) and `EloSnapshot` | Mock `RatingProvider` for now. Batch workload; may later be Python and reuse `research/` code. |
| `ingestion-service` | Adapters to external football data APIs | Anti-corruption layer: untrusted external data is validated before it is turned into domain events. |
| `dividend-service` | Per-period payout calculation | Computes the payout plan only. **`market-service` applies it to the ledger.** |
| `audit-service` | Hash-chained, tamper-evident event log | Pure consumer; nothing depends on it. |
| `gateway` | Edge routing (Spring Cloud Gateway) | Rate limiting, token relay, edge security headers. |
| Keycloak | Identity, login, MFA, roles | Off-the-shelf OAuth2/OIDC provider. We do not build authentication ourselves. |

### 2. The ledger is never split across services

Trading, curve supply and the ledger are kept in `market-service`. Splitting them would turn every trade into a distributed transaction (a saga with compensating actions). For money, partial failures in a saga cause double-spends, phantom shares and reconciliation incidents. Keeping them together costs only a larger single service.

### 3. PostgreSQL is the source of truth; Kafka is the transport

- Balances live in an ACID, append-only, double-entry ledger in PostgreSQL.
- Committed ledger and trade changes are published to Kafka via the **transactional outbox** pattern. The event is written to an outbox table in the same transaction as the business change, then relayed to Kafka. So an event is never published for a change that rolled back, and a committed change is never left without its event.
- Kafka is **not** the system of record for balances. Rebuilding balances from the event stream (full event sourcing) makes the pre-trade balance check eventually consistent, and that is unacceptable for money.

### 4. Consumers are idempotent

Kafka delivers at least once. Every consumer that causes side effects deduplicates by event ID, which gives exactly-once *effects*. This matters most when `market-service` applies dividend payouts.

### 5. Main event flow

```
ingestion-service ──match.completed──▶ rating-service ──rating.snapshot.published──▶ dividend-service
                                                                                      market-service
market-service ──trade.executed / ledger.entry.posted──▶ audit-service, dividend-service
dividend-service ──dividend.payout.requested──▶ market-service (applies to ledger, idempotently)
```

Events are JSON with an explicit `schemaVersion` field. A schema registry (Avro or Protobuf) will be adopted once more than one language consumes a topic.

## Consequences

**Positive**
- Money correctness rests on local ACID transactions, the simplest and best-understood guarantee available.
- Every non-money concern can be deployed, scaled and failed independently.
- The design exercises transferable industry patterns: outbox, idempotent consumers, anti-corruption layer, OAuth2 resource servers and service-to-service client credentials.

**Negative / accepted costs**
- Distributed tracing is required from day one (OpenTelemetry, Prometheus, Grafana). Without it, cross-service requests cannot be debugged.
- Local development needs a heavier stack (Docker Compose, later Kubernetes via kind or k3d).
- Data outside the money core is eventually consistent. For example, a new Elo snapshot reaches `market-service` with some delay. Dividends always settle against an explicitly referenced snapshot ID, never "the latest", so the delay cannot change a payout.
- `market-service` is the largest service and will remain so. This is intentional.

## Alternatives considered

- **Modular monolith for everything.** Simpler, and often the right first step in industry. Rejected because exercising service boundaries, async messaging and service-to-service security is an explicit project goal, and the non-money boundaries here are real, not artificial.
- **Separate `ledger-service` and `trading-service`.** Rejected: see Decision §2.
- **Kafka as the source of truth (full event sourcing of balances).** Rejected: see Decision §3.
- **Distributed SQL (CockroachDB, YugabyteDB).** Rejected: solves a multi-region problem this system does not have. A single PostgreSQL node per service has ample headroom.
