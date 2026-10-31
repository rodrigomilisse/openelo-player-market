package com.openelo.market.trading.curve;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;
import com.openelo.market.pricing.ShareService;

import java.util.ArrayList;

import com.openelo.market.trading.ATransaction;
import com.openelo.market.trading.Platform;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "redeems")
public class Redeem extends ATransaction<Redeem> {

	protected Redeem() {

	}

	public Redeem(ShareService shareService, Platform platform, Id<IAccount> userAccount, long shareAmount, Id<IAsset> playerShare,
			long creditAmount) {

		this.postings = new ArrayList<>(4);

		Posting sharesToPool = new Posting(userAccount, shareService.getPoolAccountId(playerShare), shareAmount,
				playerShare);
		Posting creditsToUser = new Posting(shareService.getPoolAccountId(playerShare), userAccount, creditAmount,
				platform.getCreditsId());

		this.postings.add(sharesToPool);
		this.postings.add(creditsToUser);
	}
}
