package com.openelo.market.trading;

import com.openelo.market.user.User;
import com.openelo.market.user.UserRepository;

import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;

@RestController
@RequestMapping("market")
public class MarketController {

	Market market;

	UserRepository userRepository;

	WalletRepository walletRepository;

	MarketController(Market market, UserRepository userRepository, WalletRepository walletRepository) {
		this.market = market;
		this.userRepository = userRepository;
		this.walletRepository = walletRepository;
	}

	record MarketRequest(UUID userId, long amount, UUID playerShare) {
	}

	// // TODO temp
	// @PostMapping("init")
	// @ResponseStatus(HttpStatus.CREATED)
	// public void init() {
	// Id<LedgerAccount> platformAccount = market.PLATFORM_ACCOUNT;
	// accountRepository.save(platformAccount);
	// }

	@PostMapping("mint")
	@ResponseStatus(HttpStatus.CREATED)
	public void mint(@RequestBody MarketRequest request) {
		Id<IAccount> account = getAccount(getUser(request.userId));
		Id<IAsset> playerShare = new Id<>(request.playerShare);
		market.mint(account, request.amount, playerShare);
	}

	@PostMapping("redeem")
	@ResponseStatus(HttpStatus.CREATED)
	public void redeem(@RequestBody MarketRequest request) {
		Id<IAccount> account = getAccount(getUser(request.userId));
		Id<IAsset> player_share = new Id<>(request.playerShare);

		market.redeem(account, request.amount, player_share);
	}

	private Id<IAccount> getAccount(User user) {
		return walletRepository.findByUserId(user.getId().value()).orElseThrow().getAccountId();
	}

	private User getUser(UUID userId) {
		return userRepository.findById(userId).orElseThrow();
	}
}
