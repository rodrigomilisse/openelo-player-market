package com.openelo.market.pricing;

import org.springframework.stereotype.Service;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Ledger;

@Service
public final class Quoter {

	private final Ledger ledger;

	private final Heat heat;

	Quoter(Ledger ledger, Heat heat) {
		this.ledger = ledger;
		this.heat = heat;
	}

	public long mint(Id<IAsset> share, long amount) {
		requirePositive(amount);
		long supply = supply(share);
		long baseCost = Curve.sum(supply, amount);
		long currentHeat = heat.current(share);
		long premium = Heat.premium(supply, amount, currentHeat);
		return Math.addExact(baseCost, premium);
	}

	public long redeem(Id<IAsset> share, long amount) {
		requirePositive(amount);
		long supply = supply(share);
		if (amount > supply) {
			throw new IllegalArgumentException("Cannot redeem " + amount + " shares, only " + supply + " exist");
		}
		long remainingSupply = Math.subtractExact(supply, amount);
		return Curve.sum(remainingSupply, amount);
	}

	private long supply(Id<IAsset> share) {
		Id<IAccount> pool = ShareService.getPoolAccountId(share);
		long poolBalance = ledger.getBalance(pool, share);
		return Math.negateExact(poolBalance);
	}

	private static void requirePositive(long amount) {
		if (amount <= 0) {
			throw new IllegalArgumentException("Amount must be positive, was " + amount);
		}
	}
}
