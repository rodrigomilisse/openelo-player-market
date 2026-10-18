package com.openelo.market.ledger;

import com.openelo.market.common.BaseEntity;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "accounts")
public class Account extends BaseEntity<IAccount> implements IAccount {

	protected Account() {
	}
}
