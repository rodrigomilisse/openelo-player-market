package com.openelo.market.ledger;

import java.util.Map;
import java.util.function.BiConsumer;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

public final class Balances {

	private final Map<Id<IAsset>, Long> balances;

	public Balances(Map<Id<IAsset>, Long> balances) {
		this.balances = Map.copyOf(balances);
	}

	public long getBalance(Id<IAsset> assetId) {
		return balances.getOrDefault(assetId, 0L);
	}

	public void forEach(BiConsumer<Id<IAsset>, Long> action) {
		balances.forEach(action);
	}
}
