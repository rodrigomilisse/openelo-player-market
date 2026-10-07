package com.openelo.market.common;

import java.util.UUID;
import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

@Converter(autoApply = true)
public class IdConverter implements AttributeConverter<Id<?>, UUID> {

	@Override
	public UUID convertToDatabaseColumn(Id<?> attribute) {
		return attribute.value();
	}

	@Override
	public Id<?> convertToEntityAttribute(UUID value) {
		return new Id<>(value);
	}
}
