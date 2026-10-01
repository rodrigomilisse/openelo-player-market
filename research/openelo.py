"""OpenELO rating stub.

Phase 1 only needs a stable interface to compare against Transfermarkt
valuations; the real Elo-derived formula (see Spec.md section 1) lands in a
later phase. Everything downstream (compare/average/correlation commands)
is written against this signature, so replacing the body here is the only
change needed to re-run the whole analysis against a real formula.
"""

import datetime


def openelo(player_name: str, as_of: datetime.date) -> float:
    return 10000.0
