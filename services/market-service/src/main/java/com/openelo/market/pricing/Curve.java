package com.openelo.market.pricing;

import org.springframework.stereotype.Component;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

// placeholder shape until the real curve is chosen (ADR-0010 open point 1)
@Component
final class Curve implements QuoteComponent {

	// credits are stored in units this fine, so every price is a multiple of it and
	// Heat's division is exact
	static final long PRICE_UNIT = 1000;

	private static final long START = Math.multiplyExact(100, PRICE_UNIT);

	private static final long SLOPE = PRICE_UNIT;

	private final ShareService shareService;

	Curve(ShareService shareService) {
		this.shareService = shareService;
	}

	// Naturally: price(supply) + price(supply + 1) + … for shareAmount shares.
	@Override
	public long walkUp(Id<IAsset> share, long shareAmount) {
		long supply = shareService.getSupply(share);
		return sumPrices(supply, shareAmount);
	}

	// Naturally: price(supply − 1) + price(supply − 2) + … for shareAmount shares, the
	// same prices a
	// walk up from (supply − shareAmount) adds.
	@Override
	public long walkDown(Id<IAsset> share, long shareAmount) {
		long supply = shareService.getSupply(share);
		long lowestPosition = Math.subtractExact(supply, shareAmount);
		return sumPrices(lowestPosition, shareAmount);
	}

	// Naturally: price(from) + price(from + 1) + … for shareAmount shares, with
	// price(position) = START + SLOPE × position.
	long sumPrices(long from, long shareAmount) {
		long startCost = Math.multiplyExact(START, shareAmount);
		long positionSum = Math.addExact(Math.multiplyExact(from, shareAmount), Series.ofIndices(shareAmount));
		long slopeCost = Math.multiplyExact(SLOPE, positionSum);
		return Math.addExact(startCost, slopeCost);
	}

	// Naturally: price(supply + index) × (firstHeat + heatPerShare × index) for every share in the
	// order, the first share having index 0, added up.
	long sumPricesTimesHeat(Id<IAsset> share, long shareAmount, long firstHeat, long heatPerShare) {
		long supply = shareService.getSupply(share);
		long indexSum = Series.ofIndices(shareAmount);
		long squareSum = Series.ofSquaredIndices(shareAmount);
		long positionTimesIndexSum = Math.addExact(Math.multiplyExact(supply, indexSum), squareSum);
		long startTimesIndex = Math.multiplyExact(START, indexSum);
		long slopeTimesIndex = Math.multiplyExact(SLOPE, positionTimesIndexSum);
		long pricesTimesIndex = Math.addExact(startTimesIndex, slopeTimesIndex);
		long pricesTimesFirstHeat = Math.multiplyExact(firstHeat, sumPrices(supply, shareAmount));
		long pricesTimesHeatStep = Math.multiplyExact(heatPerShare, pricesTimesIndex);
		return Math.addExact(pricesTimesFirstHeat, pricesTimesHeatStep);
	}

	private static final class Series {

		private Series() {
		}

		// Naturally: 0 + 1 + … + (count − 1). The product is always even, so the
		// halving is exact.
		static long ofIndices(long count) {
			long lastIndex = Math.subtractExact(count, 1);
			long product = Math.multiplyExact(count, lastIndex);
			return Math.divideExact(product, 2);
		}

		// Naturally: 0² + 1² + … + (count − 1)². The product is always divisible by 6,
		// so the
		// division is exact.
		static long ofSquaredIndices(long count) {
			long lastIndex = Math.subtractExact(count, 1);
			long doubleCountLessOne = Math.subtractExact(Math.multiplyExact(2, count), 1);
			long lastIndexTimesCount = Math.multiplyExact(lastIndex, count);
			long product = Math.multiplyExact(lastIndexTimesCount, doubleCountLessOne);
			return Math.divideExact(product, 6);
		}
	}
}
