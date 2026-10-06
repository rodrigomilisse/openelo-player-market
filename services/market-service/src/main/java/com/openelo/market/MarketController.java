package com.openelo.market;

import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.ledger.PlatformAccount;
import com.openelo.market.ledger.UserAccount;
import com.openelo.market.ledger.UserAccountRepository;

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
		market.mint(account, request.amount, request.playerShare);
	}

	@PostMapping("redeem")
	@ResponseStatus(HttpStatus.CREATED)
	public void redeem(@RequestBody MarketRequest request) {
		UserAccount account = getAccount(getUser(request.userId));
		market.redeem(account, request.amount, request.playerShare);
	}

	private UserAccount getAccount(User user) {
		return userAccountRepository.findByOwnerId(user.getId()).orElseThrow();
	}

	private User getUser(UUID userId) {
		return userRepository.findById(userId).orElseThrow();
	}
}
