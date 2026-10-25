package com.openelo.market.pricing;

import org.springframework.stereotype.Service;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Ledger;

import jakarta.transaction.Transactional;

@Service
public class ShareService {

	private final Ledger ledger;

	public ShareService(Ledger ledger) {
		this.ledger = ledger;
	}

	// the share takes the id of the account it opens, so finding a share's pool
	// needs no lookup
	@Transactional
	public Id<IAsset> listShare() {
		return new Id<>(ledger.openAccount().value());
	}

	public static Id<IAccount> getPoolAccountId(Id<IAsset> share) {
		return new Id<>(share.value());
	}
}
