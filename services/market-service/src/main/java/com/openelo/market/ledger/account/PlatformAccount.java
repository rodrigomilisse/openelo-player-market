package com.openelo.market.ledger.account;

import java.util.UUID;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "platform_account")
public class PlatformAccount extends AAccount {

	public static final IAccount ID = new PlatformAccount(new UUID(0, 0));

	protected PlatformAccount() {

	}

	public PlatformAccount(UUID platformUUID) {
		super(platformUUID);
	}

}
