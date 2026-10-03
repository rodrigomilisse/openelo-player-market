# ADR-0002: Entity references — relations vs. IDs

- **Status**: Accepted
- **Date**: 2026-10-01

## Context

Entities reference each other via FK columns. JPA lets us model these as
object relations (@ManyToOne) or plain ID fields. JPA's to-one default
is EAGER, which causes N+1 queries.

## Decision

- Within a module, FKs are mapped as relations, always
  `fetch = FetchType.LAZY`, with `fetch` written explicitly everywhere.
- Across module boundaries, FKs are plain UUID fields; no navigation.
- Queries that need related data fetch it explicitly (@EntityGraph / JOIN FETCH).
- Setting a relation from an ID uses `getReferenceById`.

## Consequences

+ No accidental eager loading; fetching is decided per query.
+ Modules stay decoupled at compile time.
  − Lazy access outside a transaction throws LazyInitializationException.
  − Cross-module lookups require an explicit repository call€€.

Entities reference each other via FK columns. JPA lets us model these as
object relations (@ManyToOne) or plain ID fields. JPA's to-one default
is EAGER, which causes N+1 queries.

## Decision

- Within a module, FKs are mapped as relations, always
  `fetch = FetchType.LAZY`, with `fetch` written explicitly everywhere.
- Across module boundaries, FKs are plain UUID fields; no navigation.
- Queries that need related data fetch it explicitly (@EntityGraph / JOIN FETCH).
- Setting a relation from an ID uses `getReferenceById`.

## Consequences

+ No accidental eager loading; fetching is decided per query.
+ Modules stay decoupled at compile time.
  − Lazy access outside a transaction throws LazyInitializationException.
  − Cross-module lookups require an explicit repository call.
