
package com.openelo.market;

import java.util.UUID;
import org.springframework.stereotype.Service;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.ledger.Mint;
import com.openelo.market.ledger.Redeem;
import com.openelo.market.ledger.UserAccount;
import com.openelo.market.ledger.UserAccountRepository;
import jakarta.transaction.Transactional;

@Service
class Market {

	UserAccountRepository userAccountRepository;

	private final Ledger ledger;

	public long quoteMint(UUID player_share) {
		return 100;
	}

	public long quoteRedeem(UUID player_share) {
		return 90;
	}

	public Market(UserAccountRepository userAccountRepository, Ledger ledger) {
		this.userAccountRepository = userAccountRepository;
		this.ledger = ledger;
	}

	@Transactional
	public void mint(User user, long amount, UUID player_share) {
		UserAccount account = userAccountRepository.findByOwnerId(user.getId()).orElseThrow();
		long pricePerShare = quoteMint(player_share);

		ledger.post(new Mint(account, amount, player_share, pricePerShare));

		// TODO persist mint
	}

	@Transactional
	public void redeem(User user, long amount, UUID player_share) {
		UserAccount account = userAccountRepository.findByOwnerId(user.getId()).orElseThrow();
		long pricePerShare = quoteRedeem(player_share);

		ledger.post(new Redeem(account, amount, player_share, pricePerShare));

		// TODO persist redemption
	}
}