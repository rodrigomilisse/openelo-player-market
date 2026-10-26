package com.openelo.market.pricing;

import org.springframework.stereotype.Component;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

@Component
final class Fee implements QuoteComponent {

	// the fee is a whole number out of FEE_SCALE; every base cost is a multiple of
	// Curve.PRICE_UNIT, so taking the rate of it is exact
	private static final long FEE_SCALE = Curve.PRICE_UNIT;

	private static final long FEE_RATE = 100;

	private final Curve curve;

	Fee(Curve curve) {
		this.curve = curve;
	}

	// Naturally: the base curve cost of the order times FEE_RATE out of FEE_SCALE.
	@Override
	public long walkUp(Id<IAsset> share, long shareAmount) {
		long baseCost = curve.walkUp(share, shareAmount);
		long scaledFee = Math.multiplyExact(baseCost, FEE_RATE);
		return Math.divideExact(scaledFee, FEE_SCALE);
	}

	// no fee on redeem (ADR-0010 §6)
	@Override
	public long walkDown(Id<IAsset> share, long shareAmount) {
		return 0;
	}

	@Override
	public QuoteRole role() {
		return QuoteRole.REVENUE;
	}
}
