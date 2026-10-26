package com.openelo.market.pricing;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;

import org.springframework.stereotype.Component;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

@Component
final class Heat implements QuoteComponent {

	private static final Duration WINDOW = Duration.ofDays(30);

	// heat is a whole number in which HEAT_SCALE means 100%; every price is a
	// multiple of
	// Curve.PRICE_UNIT, so removing the scale from a price times a heat is exact
	private static final long HEAT_SCALE = Curve.PRICE_UNIT;

	private static final long HEAT_PER_SHARE = 1;

	private final ShareService shareService;

	private final Curve curve;

	private final Clock clock;

	Heat(ShareService shareService, Curve curve, Clock clock) {
		this.shareService = shareService;
		this.curve = curve;
		this.clock = clock;
	}

	// TODO revisit how the heat is calculated (see the pricing README)
	// Naturally: every share pays its price times its heat, which is HEAT_PER_SHARE
	// for each share
	// before it (the ones minted inside the window plus the ones ahead of it in the
	// same order),
	// out of HEAT_SCALE.
	@Override
	public long walkUp(Id<IAsset> share, long shareAmount) {
		long recentShares = shareService.getMintedSince(share, currentWindowStart());
		long firstHeat = Math.multiplyExact(recentShares, HEAT_PER_SHARE);
		long scaledPremium = curve.sumPricesTimesHeat(share, shareAmount, firstHeat, HEAT_PER_SHARE);
		return Math.divideExact(scaledPremium, HEAT_SCALE);
	}

	// redeem pays the base curve only (ADR-0010 §5)
	@Override
	public long walkDown(Id<IAsset> share, long shareAmount) {
		return 0;
	}

	// the start of the window that is open now
	private Instant currentWindowStart() {
		return clock.instant().minus(WINDOW);
	}
}
