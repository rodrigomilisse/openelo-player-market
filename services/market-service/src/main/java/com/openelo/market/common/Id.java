package com.openelo.market.common;

import java.util.Objects;
import java.util.UUID;

public record Id<T>(UUID value) {

	public Id {
		Objects.requireNonNull(value);
	}
}
