package com.openelo.market.ledger;

import java.util.function.Function;
import java.util.UUID;
import jakarta.persistence.AttributeConverter;

public abstract class IdConverter<T extends Id> implements AttributeConverter<T, UUID> {

	Function<UUID, T> wrap;

	@Override
	public UUID convertToDatabaseColumn(Id atribute) {
		return atribute.value();
	}

	@Override
	public T convertToEntityAttribute(UUID value) {
		return wrap.apply(value);
	}

}
