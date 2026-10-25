package com.openelo.market.pricing;

import java.time.Clock;

import org.springframework.stereotype.Service;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.Ledger;

@Service
public class Quoter {

	private static final long START_PRICE = 100;

	private final Ledger ledger;

	private final Clock clock;

	public Quoter(Ledger ledger, Clock clock) {
		this.ledger = ledger;
		this.clock = clock;
	}

	public long mint(Id<IAsset> share, long amount) {
		requirePositive(amount);
		return Curve.sum(START_PRICE, supply(share), amount);
	}

	public long redeem(Id<IAsset> share, long amount) {
		requirePositive(amount);
		long supply = supply(share);
		if (amount > supply) {
			throw new IllegalArgumentException("Cannot redeem " + amount + " shares, only " + supply + " exist");
		}
		return Curve.sum(START_PRICE, supply - amount, amount);
	}

	private long supply(Id<IAsset> share) {
		return -ledger.getBalance(ShareService.getPoolAccountId(share), share);
	}

	private static void requirePositive(long amount) {
		if (amount <= 0) {
			throw new IllegalArgumentException("Amount must be positive, was " + amount);
		}
	}
}
