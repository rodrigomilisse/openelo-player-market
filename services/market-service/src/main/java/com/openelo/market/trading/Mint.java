package com.openelo.market.trading;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;
import com.openelo.market.pricing.Quote;
import com.openelo.market.pricing.ShareService;
import java.util.ArrayList;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "mints")
public class Mint extends ATransaction<Mint> {

	protected Mint() {

	}

	public Mint(ShareService shareService, Id<IAccount> userAccount, long shareAmount, Id<IAsset> playerShare,
			Quote quote) {

		this.postings = new ArrayList<>(4);

		Id<IAccount> poolAccount = shareService.getPoolAccountId(playerShare);
		Posting backingToPool = new Posting(userAccount, poolAccount, quote.backing(), Market.CREDITS);
		Posting revenueToPlatform = new Posting(userAccount, Market.PLATFORM_ACCOUNT_ID, quote.revenue(),
				Market.CREDITS);
		Posting sharesToUser = new Posting(poolAccount, userAccount, shareAmount, playerShare);

		this.postings.add(backingToPool);
		this.postings.add(revenueToPlatform);
		this.postings.add(sharesToUser);
	}
}
