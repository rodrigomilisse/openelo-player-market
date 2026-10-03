package com.openelo.market;

import java.util.UUID;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.ledger.PlatformAccount;

@RestController
@RequestMapping("market")
public class MarketController {

	@Autowired
	Market market;

	// TODO temp
	@Autowired
	AccountRepository accountRepository;

	@Autowired
	UserRepository users;

	public MarketController(Market market, AccountRepository accountRepository, UserRepository userRepository) {
		this.market = market;
		this.accountRepository = accountRepository;
		this.users = userRepository;
	}

	record MarketRequest(UUID user, long amount, UUID playerShare) {
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
		User user = users.findById(request.user).orElseThrow();
		market.mint(user, request.amount, request.playerShare);
	}

	@PostMapping("redeem")
	@ResponseStatus(HttpStatus.CREATED)
	public void redeem(@RequestBody MarketRequest request) {
		User user = users.findById(request.user).orElseThrow();
		market.redeem(user, request.amount, request.playerShare);
	}
}
