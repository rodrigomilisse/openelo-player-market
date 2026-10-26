package com.openelo.market.pricing;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;

import org.springframework.stereotype.Component;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Ledger;

@Component
final class Heat {

	private static final Duration WINDOW = Duration.ofDays(30);

	// heat is a whole number in which HEAT_SCALE means 100%; every price is a multiple of
	// Curve.PRICE_UNIT, so removing the scale from a price times a heat is exact
	private static final long HEAT_SCALE = Curve.PRICE_UNIT;

	private static final long HEAT_PER_SHARE = 1;

	private final Ledger ledger;

	private final Clock clock;

	Heat(Ledger ledger, Clock clock) {
		this.ledger = ledger;
		this.clock = clock;
	}

	// the share's heat right now: HEAT_PER_SHARE for each share minted inside the window
	long current(Id<IAsset> share) {
		long recentShares = recentShares(share);
		return Math.multiplyExact(recentShares, HEAT_PER_SHARE);
	}

	// Naturally: every share pays its price times its heat, which starts at currentHeat and grows by
	// HEAT_PER_SHARE for each share ahead of it in the same order, out of HEAT_SCALE.
	static long premium(long supply, long amount, long currentHeat) {
		long scaledPremium = Curve.sumWeighted(supply, amount, currentHeat, HEAT_PER_SHARE);
		return Math.divideExact(scaledPremium, HEAT_SCALE);
	}

	// only mints move shares out of the pool, so its outflow since the window started is the recent mints
	private long recentShares(Id<IAsset> share) {
		Id<IAccount> pool = ShareService.getPoolAccountId(share);
		Instant windowStart = clock.instant().minus(WINDOW);
		return ledger.getOutflow(pool, share, windowStart);
	}
}
