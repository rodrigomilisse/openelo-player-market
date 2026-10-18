package com.openelo.market.trading;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;
import java.util.ArrayList;
import java.util.UUID;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "mints")
public class Mint extends ATransaction<Mint> {

	private UUID userAccountId;

	protected Mint() {

	}

	public Mint(Id<IAccount> userAccount, long shareAmount, Id<IAsset> playerShare, long pricePerShare) {

		this.userAccountId = userAccount.value();
		this.postings = new ArrayList<>(4);

		long creditAmount = Math.multiplyExact(shareAmount, pricePerShare);

		Posting creditsToPlatform = new Posting(userAccount, Market.PLATFORM_ACCOUNT_ID, creditAmount, Market.CREDITS);
		Posting sharesToUser = new Posting(Market.PLATFORM_ACCOUNT_ID, userAccount, shareAmount,
				playerShare);

		this.postings.add(creditsToPlatform);
		this.postings.add(sharesToUser);
	}

	public Id<IAccount> getUserAccount() {
		return new Id<>(userAccountId);
	}
}
