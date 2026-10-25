# ledger

Generic double-entry core: accounts, transactions and postings (ADR-0003, ADR-0007).

## Planned, not built

Writes go through one gate. Today `Ledger.post` is public, and two places call it: `Market` (mint and redeem) and `BankService` (deposit and withdraw).

- **Gate:** a sealed abstract `LedgerWriter` in `trading`, with `permits Market, BankService`. A sealed class can only be extended by the classes it names, so nothing else can become a writer.
- **Call restriction:** sealing doesn't stop a class from calling `Ledger.post` directly, so an ArchUnit test would fail the build if any class other than the gate calls it.
- **Flow:** every write is quote, then post, through the gate.

Open:
- `Ledger.openAccount` is a write too, but it isn't a posting, so it's outside this gate for now.
- `Market` and `BankService` must be `non-sealed` rather than `final`, because Spring subclasses them for `@Transactional`.
