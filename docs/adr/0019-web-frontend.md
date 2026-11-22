# ADR-0019: Web frontend

- **Status**: Proposed, not yet implemented. Each item is marked decided,
  proposed or open.
- **Date**: 2026-11-17

## Context

`frontend/README.md` planned a thin client once the backend API is stable.
A web version is wanted before the mobile app, which will be native per
platform rather than a cross-platform framework, so the web client and the
apps share no code. What they share is the HTTP API.

Today `market-service` offers sign-up, a user list, balances
(ADR-0016), bank deposit and withdraw, curve mint and redeem, and P2P place
and cancel. A product screen also needs reads that do not exist yet: a share
catalogue linked to players, quote and supply (both `501`, ADR-0016 decision
3), order book depth, a user's open orders, and price history. There is no
authentication yet; requests carry `userId` in the body.

## Decision

### Decided

1. **A web client is built now, ahead of the native apps**, as a product UI,
   not a developer console.
2. **Stack: React, TypeScript and Vite**, a single-page app. No server
   rendering: every screen is behind a user, so there is nothing to index and
   no gain from rendering on a server.
3. **Endpoints that do not exist yet are mocked**, so the UI can be built
   ahead of them.
4. **One credit is 100,000 units of an amount**: 100 times
   `Curve.PRICE_UNIT` (1,000), so a share's starting curve price
   (`Curve.START`) is one credit.
5. **Amounts stay JSON numbers, below 2^53.** JavaScript reads integers up to
   2^53 exactly; the API guarantees amounts stay below it rather than
   serialising them as strings.

### Proposed

6. **The client lives in `frontend/web`**, leaving room for the native apps
   beside it.
7. **The OpenAPI document is the contract between backend and every
   client.** `market-service` adds springdoc to publish it from the
   controllers' records. The web client generates its types from it
   (`openapi-typescript`); native apps can generate theirs from the same
   document. A renamed field breaks the client's build instead of failing at
   runtime.
8. **Mocks intercept at the network layer** with Mock Service Worker: the
   client calls real URLs, and in development a handler answers the ones the
   backend lacks. Calls the backend serves pass through to it. When an
   endpoint ships, its handler is deleted and no client code changes.
9. **A mocked endpoint's shape is a draft, not a decision.** Each one is
   decided by the backend ADR that introduces the endpoint; the client
   follows that decision.
10. **Server state goes through TanStack Query**: balances load when the app
   opens, refetch in the background, and are invalidated after a write
   (ADR-0016's usage pattern).
11. **Every write sends an `Idempotency-Key`**, a UUID generated per user
   action and reused on retry (ADR-0004), though the server does not check it
   yet.
12. **Money stays integer in the client.** Amounts are formatted from integer
    minor units by integer division and remainder, never by dividing a
    float.
13. **In development the Vite server proxies API calls to `market-service`**,
    so the browser sees one origin and the backend needs no CORS
    configuration. In deployment, `gateway` takes that role.
14. **Until authentication exists the client picks a user** from
    `GET users`. Keycloak login replaces this (ADR-0001).

## Consequences

+ The UI can be built and shown before the read side is complete.
+ Web and native clients share one machine-readable contract.
+ Removing a mock is a deletion, not a change to client code.
  − Mocked shapes may differ from what the backend decides; screens using
  them are reworked when it does.
  − `market-service` gains a dependency (springdoc) for the contract.

## Alternatives considered

- **Next.js**: server rendering and a Node server, with little to gain behind
  a login.
- **A shared cross-platform client (React Native)**: the apps will be native.
- **Developer console against today's API only**: rejected in favour of a
  product UI with mocks.
- **Mocks inside the client code** (fake fetch functions): every one must be
  rewritten when its endpoint ships.
- **Hand-written client types**: drift from the backend silently.

- **Amounts as JSON strings**: exact at any size, but a breaking change to
  every endpoint carrying money, for balances that never approach 2^53.
