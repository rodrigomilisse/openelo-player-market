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

	// heat is an integer in which HEAT_SCALE means 100%; every price is a multiple of
	// Curve.PRICE_UNIT, so removing the scale from a price times a heat is exact
	private static final long HEAT_SCALE = Curve.PRICE_UNIT;

	// each share adds 0.1% of heat, written as a division of the price unit so the rate stays an
	// integer
	private static final long HEAT_RATE = Math.divideExact(Curve.PRICE_UNIT, 1000);

	private final ShareService shareService;

	private final Curve curve;

	private final Clock clock;

	Heat(ShareService shareService, Curve curve, Clock clock) {
		this.shareService = shareService;
		this.curve = curve;
		this.clock = clock;
	}

	// TODO revisit how the heat is calculated (see the pricing README)
	// Naturally: every share pays its price times its heat, which is HEAT_RATE
	// for each share
	// before it (the ones minted inside the window plus the ones ahead of it in the
	// same order),
	// out of HEAT_SCALE.
	@Override
	public long walkUp(Id<IAsset> share, long shareAmount) {
		long recentShares = shareService.getMintedSince(share, currentWindowStart());
		long firstHeat = Math.multiplyExact(recentShares, HEAT_RATE);
		long scaledPremium = curve.sumPricesTimesHeat(share, shareAmount, firstHeat, HEAT_RATE);
		return Math.divideExact(scaledPremium, HEAT_SCALE);
	}

	// redeem pays the base curve only (ADR-0010 §5)
	@Override
	public long walkDown(Id<IAsset> share, long shareAmount) {
		return 0;
	}

	@Override
	public QuoteRole role() {
		return QuoteRole.REVENUE;
	}

	// the start of the window that is open now
	private Instant currentWindowStart() {
		return clock.instant().minus(WINDOW);
	}
}
