package com.openelo.market.trading.p2p;

import java.util.UUID;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import jakarta.persistence.Embeddable;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;

@Embeddable
record Level(UUID shareId, @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.NAMED_ENUM) Side side,
		long limitPrice) {
}
