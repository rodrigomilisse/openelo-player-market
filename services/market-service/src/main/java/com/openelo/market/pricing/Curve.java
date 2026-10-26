package com.openelo.market.pricing;

// placeholder shape until the real curve is chosen (ADR-0010 open point 1)
final class Curve {

	// credits are stored in units this fine, so every price is a multiple of it and Heat's division is exact
	static final long PRICE_UNIT = 1000;

	private static final long START = Math.multiplyExact(100, PRICE_UNIT);

	private static final long SLOPE = PRICE_UNIT;

	private Curve() {
	}

	// Naturally: price(from) + price(from + 1) + … for count shares, with
	// price(position) = START + SLOPE × position.
	static long sum(long from, long count) {
		long positions = Math.addExact(Math.multiplyExact(from, count), Series.ofIndices(count));
		long startCost = Math.multiplyExact(START, count);
		long slopeCost = Math.multiplyExact(SLOPE, positions);
		return Math.addExact(startCost, slopeCost);
	}

	// Naturally: price(from + index) × (baseWeight + weightPerIndex × index) for every share in
	// the order, the first share having index 0, added up.
	static long sumWeighted(long from, long count, long baseWeight, long weightPerIndex) {
		long indexSum = Series.ofIndices(count);
		long squareSum = Series.ofSquaredIndices(count);
		long weightedPositions = Math.addExact(Math.multiplyExact(from, indexSum), squareSum);
		long startWeighted = Math.multiplyExact(START, indexSum);
		long slopeWeighted = Math.multiplyExact(SLOPE, weightedPositions);
		long indexWeightedPrices = Math.addExact(startWeighted, slopeWeighted);
		long pricesWeightedByBase = Math.multiplyExact(baseWeight, sum(from, count));
		long pricesWeightedByIndex = Math.multiplyExact(weightPerIndex, indexWeightedPrices);
		return Math.addExact(pricesWeightedByBase, pricesWeightedByIndex);
	}

	private static final class Series {

		private Series() {
		}

		// Naturally: 0 + 1 + … + (count − 1). The product is always even, so the halving is exact.
		static long ofIndices(long count) {
			long lastIndex = Math.subtractExact(count, 1);
			long product = Math.multiplyExact(count, lastIndex);
			return Math.divideExact(product, 2);
		}

		// Naturally: 0² + 1² + … + (count − 1)². The product is always divisible by 6, so the
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
