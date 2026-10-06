package com.openelo.market.ledger;

import java.util.Objects;
import java.util.UUID;

public record AssetId(UUID value) {

	public static final AssetId CREDITS = new AssetId(new UUID(0, 0));

	public AssetId {
		Objects.requireNonNull(value);
	}
}
