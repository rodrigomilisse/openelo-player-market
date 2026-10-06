package com.openelo.market.ledger;

import java.util.UUID;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

@Converter(autoApply = true)
public class AssetIdConverter implements AttributeConverter<AssetId, UUID> {
	@Override
	public UUID convertToDatabaseColumn(AssetId atribute) {
		return atribute.value();
	}

	@Override
	public AssetId convertToEntityAttribute(UUID dbdata) {
		return new AssetId(dbdata);
	}
}
