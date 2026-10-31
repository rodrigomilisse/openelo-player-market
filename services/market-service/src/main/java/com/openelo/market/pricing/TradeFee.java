package com.openelo.market.pricing;

import java.math.BigInteger;

import org.springframework.stereotype.Component;

// Charged to the taker of a P2P trade only (ADR-0010).
@Component
final class TradeFee {

	private static final long FEE_SCALE = Curve.PRICE_UNIT;

	// 5% of the scale, written as a division of the price unit so the rate stays an integer
	private static final long FEE_RATE = Math.divideExact(Curve.PRICE_UNIT, 20);

	// The fee is whole when price × FEE_RATE is a multiple of FEE_SCALE; the smallest
	// price step with that property is FEE_SCALE / gcd(FEE_SCALE, FEE_RATE).
	static final long TICK = Math.divideExact(FEE_SCALE,
			BigInteger.valueOf(FEE_SCALE).gcd(BigInteger.valueOf(FEE_RATE)).longValueExact());

	long of(long tradeValue) {
		long scaledFee = Math.multiplyExact(tradeValue, FEE_RATE);
		return Math.divideExact(scaledFee, FEE_SCALE);
	}
}
