
package com.openelo.market;

import java.util.UUID;
import org.springframework.stereotype.Service;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.ledger.Mint;
import com.openelo.market.ledger.Redeem;
import com.openelo.market.ledger.UserAccount;
import jakarta.transaction.Transactional;

@Service
class Market {

	private final Ledger ledger;

	public long quoteMint(UUID player_share) {
		return 100;
	}

	public long quoteRedeem(UUID player_share) {
		return 90;
	}

	public Market(Ledger ledger) {
		this.ledger = ledger;
	}

	@Transactional
	public void mint(UserAccount userAccount, long amount, UUID player_share) {
		long pricePerShare = quoteMint(player_share);
		ledger.post(new Mint(userAccount, amount, player_share, pricePerShare));
	}

	@Transactional
	public void redeem(UserAccount userAccount, long amount, UUID player_share) {
		long pricePerShare = quoteRedeem(player_share);
		ledger.post(new Redeem(userAccount, amount, player_share, pricePerShare));
	}
}