package com.openelo.market.pricing;

// placeholder shape until the real curve is chosen (ADR-0010 open point 1)
final class Curve {

	static final long SLOPE = 1;

	private Curve() {
	}

	// price(from) + … + price(from + count − 1) in closed form, where price(i) = start + SLOPE × i.
	// count × (count − 1) is always even, so the halving is exact.
	static long sum(long start, long from, long count) {
		long positions = Math.addExact(Math.multiplyExact(count, from), Math.multiplyExact(count, count - 1) / 2);
		return Math.addExact(Math.multiplyExact(count, start), Math.multiplyExact(SLOPE, positions));
	}
}
