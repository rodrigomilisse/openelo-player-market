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
@Table(name = "redeems")
public class Redeem extends ATransaction<Redeem> {

	private UUID userAccountId;

	protected Redeem() {

	}

	public Redeem(Id<IAccount> userAccount, long shareAmount, Id<IAsset> playerShare, long pricePerShare) {
		this.userAccountId = userAccount.value();

		this.postings = new ArrayList<>(4);

		long creditAmount = Math.multiplyExact(shareAmount, pricePerShare);

		Posting sharesToPlatform = new Posting(userAccount, Market.PLATFORM_ACCOUNT_ID, shareAmount, playerShare);
		Posting creditsToUser = new Posting(Market.PLATFORM_ACCOUNT_ID, userAccount, creditAmount,
				Market.CREDITS);

		this.postings.add(sharesToPlatform);
		this.postings.add(creditsToUser);
	}

	public Id<IAccount> getUserAccount() {
		return new Id<>(this.userAccountId);
	}
}
