"""Shared helpers for turning stored market-value rows into time series that
can be plotted/correlated against OpenELO, plus the lead/lag correlation
analysis used to answer "does OpenELO need a phase shift".
"""

import sqlite3

import numpy as np
import pandas as pd

import db
from openelo import openelo


def market_value_series(conn: sqlite3.Connection, player_id: int) -> pd.Series:
    """Monthly-resampled (forward-filled) market value series in EUR."""
    rows = db.get_market_values(conn, player_id)
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series(
        {pd.to_datetime(r["date"]): r["market_value_eur"] for r in rows}
    ).sort_index()
    s = s.dropna()
    if s.empty:
        return s
    monthly = s.resample("MS").mean().ffill()
    return monthly


def openelo_series(player_name: str, index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series({d: openelo(player_name, d.date()) for d in index})


def player_frame(conn: sqlite3.Connection, player_row: sqlite3.Row) -> pd.DataFrame:
    """DataFrame indexed by month with 'market_value_eur' and 'openelo' columns."""
    mv = market_value_series(conn, player_row["id"])
    if mv.empty:
        return pd.DataFrame(columns=["market_value_eur", "openelo"])
    oe = openelo_series(player_row["name"], mv.index)
    return pd.DataFrame({"market_value_eur": mv, "openelo": oe})


def average_frame(conn: sqlite3.Connection, player_rows: list[sqlite3.Row]) -> pd.DataFrame:
    """Average market value and average OpenELO across players, aligned by
    calendar month (only months where at least one player has data)."""
    frames = []
    for p in player_rows:
        f = player_frame(conn, p)
        if not f.empty:
            frames.append(f)
    if not frames:
        return pd.DataFrame(columns=["market_value_eur", "openelo", "n_players"])

    mv_concat = pd.concat([f["market_value_eur"] for f in frames], axis=1)
    oe_concat = pd.concat([f["openelo"] for f in frames], axis=1)
    out = pd.DataFrame(
        {
            "market_value_eur": mv_concat.mean(axis=1),
            "openelo": oe_concat.mean(axis=1),
            "n_players": mv_concat.count(axis=1),
        }
    ).sort_index()
    return out


def lagged_cross_correlation(
    series_a: pd.Series, series_b: pd.Series, max_lag_months: int = 12
) -> pd.DataFrame:
    """Pearson correlation between series_a and series_b shifted by each lag
    in [-max_lag_months, max_lag_months] (in months). A positive lag means
    series_b is shifted forward in time relative to series_a — i.e. series_b
    at time t is compared to series_a at time t - lag (series_a leads).

    Returns a DataFrame with columns ['lag_months', 'pearson_r', 'n_obs'].
    """
    a = series_a.copy()
    b = series_b.copy()
    a.index = pd.to_datetime(a.index)
    b.index = pd.to_datetime(b.index)

    results = []
    for lag in range(-max_lag_months, max_lag_months + 1):
        shifted_b = b.copy()
        shifted_b.index = shifted_b.index - pd.DateOffset(months=lag)
        joined = pd.concat([a, shifted_b], axis=1, join="inner").dropna()
        if len(joined) < 3:
            results.append({"lag_months": lag, "pearson_r": np.nan, "n_obs": len(joined)})
            continue
        col_a, col_b = joined.iloc[:, 0], joined.iloc[:, 1]
        if col_a.std() == 0 or col_b.std() == 0:
            r = np.nan
        else:
            r = float(np.corrcoef(col_a, col_b)[0, 1])
        results.append({"lag_months": lag, "pearson_r": r, "n_obs": len(joined)})
    return pd.DataFrame(results)


def best_lag(cross_corr: pd.DataFrame) -> pd.Series | None:
    valid = cross_corr.dropna(subset=["pearson_r"])
    if valid.empty:
        return None
    return valid.loc[valid["pearson_r"].abs().idxmax()]
