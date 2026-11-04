package com.openelo.market.ledger;

import java.io.Serializable;
import java.util.UUID;

import jakarta.persistence.Embeddable;

@Embeddable
public record AccountBalanceKey(UUID accountId, UUID assetId) implements Serializable {
}
