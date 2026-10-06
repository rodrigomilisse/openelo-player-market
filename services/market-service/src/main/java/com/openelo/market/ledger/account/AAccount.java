package com.openelo.market.ledger.account;

import java.util.UUID;
import com.openelo.market.BaseEntity;
import jakarta.persistence.Entity;
import jakarta.persistence.Inheritance;
import jakarta.persistence.InheritanceType;
import jakarta.persistence.Table;

@Entity
@Table(name = "accounts")
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class AAccount extends BaseEntity implements IAccount {

	protected AAccount() {

	}

	protected AAccount(UUID id) {
		super(id);
	}
}
