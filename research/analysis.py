"""Shared helpers for turning stored market-value rows into time series that
can be plotted/correlated against OpenELO, plus the lead/lag correlation
analysis used to answer "does OpenELO need a phase shift".

Set A's market values come from the tracked scrape (db.py); set B's from the
research store (store.py). OpenElo is in Elo points here, for plotting.
"""

import sqlite3

import numpy as np
import pandas as pd

import db
import store
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


def research_market_value_series(tm_id: int) -> pd.Series:
    """Set B: the same monthly series from transfermarkt-datasets' valuations."""
    rows = store.query("SELECT date, value_eur FROM valuation WHERE player_id = ? ORDER BY date", (int(tm_id),))
    if rows.empty:
        return pd.Series(dtype=float)
    s = pd.Series(rows.value_eur.to_numpy(dtype=float), index=pd.to_datetime(rows.date)).sort_index()
    return s.resample("MS").mean().ffill()


def openelo_series(tm_id: int, index: pd.DatetimeIndex) -> pd.Series:
    values = {}
    for d in index:
        rating = openelo(tm_id, d.date())
        values[d] = rating / 1000 if rating is not None else np.nan
    return pd.Series(values, dtype=float)


def frame_from(mv: pd.Series, tm_id: int) -> pd.DataFrame:
    """DataFrame indexed by month with 'market_value_eur' and 'openelo' columns."""
    if mv.empty:
        return pd.DataFrame(columns=["market_value_eur", "openelo"])
    return pd.DataFrame({"market_value_eur": mv, "openelo": openelo_series(tm_id, mv.index)})


def player_frame(conn: sqlite3.Connection, player_row: sqlite3.Row) -> pd.DataFrame:
    return frame_from(market_value_series(conn, player_row["id"]), int(player_row["tm_id"]))


def set_b_frame(tm_id: int) -> pd.DataFrame:
    return frame_from(research_market_value_series(tm_id), tm_id)


def average_frame(conn: sqlite3.Connection | None, player_rows: list) -> pd.DataFrame:
    """Average market value and average OpenELO across players, aligned by
    calendar month (only months where at least one player has data). Rows are
    set A store rows, or set B Transfermarkt ids when conn is None."""
    frames = []
    for p in player_rows:
        f = player_frame(conn, p) if conn is not None else set_b_frame(p)
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
