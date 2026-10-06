package com.openelo.market.trading;

import com.openelo.market.ledger.account.AccountRepository;
import com.openelo.market.user.User;
import com.openelo.market.user.UserRepository;

import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.ledger.AssetId;
import com.openelo.market.ledger.account.PlatformAccount;
import com.openelo.market.ledger.account.UserAccount;
import com.openelo.market.ledger.account.UserAccountRepository;

@RestController
@RequestMapping("market")
public class MarketController {

	Market market;

	// TODO temp
	AccountRepository accountRepository;

	UserRepository userRepository;

	UserAccountRepository userAccountRepository;

	public MarketController(Market market, AccountRepository accountRepository, UserRepository userRepository) {
		this.market = market;
		this.accountRepository = accountRepository;
		this.userRepository = userRepository;
	}

	record MarketRequest(UUID userId, long amount, UUID playerShare) {
	}

	// TODO temp
	@PostMapping("init")
	@ResponseStatus(HttpStatus.CREATED)
	public void init() {
		PlatformAccount platformAccount = new PlatformAccount(new UUID(0, 0));
		accountRepository.save(platformAccount);
	}

	@PostMapping("mint")
	@ResponseStatus(HttpStatus.CREATED)
	public void mint(@RequestBody MarketRequest request) {
		UserAccount account = getAccount(getUser(request.userId));
		AssetId playerShare = new AssetId(request.playerShare);
		market.mint(account, request.amount, playerShare);
	}

	@PostMapping("redeem")
	@ResponseStatus(HttpStatus.CREATED)
	public void redeem(@RequestBody MarketRequest request) {
		UserAccount account = getAccount(getUser(request.userId));
		AssetId player_share = new AssetId(request.playerShare);

		market.redeem(account, request.amount, player_share);
	}

	private UserAccount getAccount(User user) {
		return userAccountRepository.findByOwnerId(user.getId()).orElseThrow();
	}

	private User getUser(UUID userId) {
		return userRepository.findById(userId).orElseThrow();
	}
}
