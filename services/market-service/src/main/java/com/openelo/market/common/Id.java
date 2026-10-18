package com.openelo.market.common;

import java.util.Objects;
import java.util.UUID;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public record Id<T>(@JsonValue UUID value) {

	@JsonCreator(mode = JsonCreator.Mode.DELEGATING)
	public Id {
		Objects.requireNonNull(value);
	}
}
