package com.openelo.market.projection;

import java.util.UUID;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;

final class BalanceHash {

	private BalanceHash() {
	}

	static String key(Id<IAccount> accountId) {
		return "balances:" + accountId.value();
	}

	// the bare UUID, not Id.toString(), which would write "Id[value=...]"
	static String toField(Id<IAsset> assetId) {
		return assetId.value().toString();
	}

	static Id<IAsset> toAsset(String field) {
		return new Id<>(UUID.fromString(field));
	}

	static String toValue(long balance) {
		return Long.toString(balance);
	}

	static long toBalance(String value) {
		return Long.parseLong(value);
	}
}
