package com.openelo.market.trading;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;
import com.openelo.market.pricing.ShareService;

import java.util.ArrayList;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "redeems")
public class Redeem extends ATransaction<Redeem> {

	protected Redeem() {

	}

	public Redeem(Id<IAccount> userAccount, long shareAmount, Id<IAsset> playerShare, long creditAmount) {

		this.postings = new ArrayList<>(4);

		Posting sharesToPool = new Posting(userAccount, ShareService.getPoolAccountId(playerShare), shareAmount, playerShare);
		Posting creditsToUser = new Posting(Market.PLATFORM_ACCOUNT_ID, userAccount, creditAmount,
				Market.CREDITS);

		this.postings.add(sharesToPool);
		this.postings.add(creditsToUser);
	}
}
