
package com.openelo.market.trading;

import java.util.UUID;
import org.springframework.stereotype.Service;

import com.openelo.market.ledger.AssetId;
import com.openelo.market.ledger.account.IAccount;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.ledger.Mint;
import com.openelo.market.ledger.account.PlatformAccount;
import com.openelo.market.ledger.Redeem;
import com.openelo.market.ledger.account.UserAccount;
import jakarta.transaction.Transactional;

@Service
class Market {

	private final Ledger ledger;

	public long quoteMint(AssetId player_share) {
		return 100;
	}

	public long quoteRedeem(AssetId player_share) {
		return 90;
	}

	public Market(Ledger ledger) {
		this.ledger = ledger;
	}

	@Transactional
	public void mint(UserAccount userAccount, long amount, AssetId player_share) {
		long pricePerShare = quoteMint(player_share);
		ledger.post(new Mint(userAccount, amount, player_share, pricePerShare));
	}

	@Transactional
	public void redeem(UserAccount userAccount, long amount, AssetId player_share) {
		long pricePerShare = quoteRedeem(player_share);
		ledger.post(new Redeem(userAccount, amount, player_share, pricePerShare));
	}
}