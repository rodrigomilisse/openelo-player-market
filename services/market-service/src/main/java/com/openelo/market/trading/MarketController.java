package com.openelo.market.trading;

import com.openelo.market.user.IUser;
import com.openelo.market.user.UserRepository;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

@RestController
@RequestMapping("market")
public class MarketController {

	Market market;

	MarketController(Market market, UserRepository userRepository, WalletRepository walletRepository) {
		this.market = market;
	}

	record MarketRequest(Id<IUser> userId, long amount, Id<IAsset> playerShare) {
	}

	@PostMapping("mint")
	@ResponseStatus(HttpStatus.CREATED)
	public void mint(@RequestBody MarketRequest request) {
		// TODO validate args
		market.mint(request.userId, request.amount, request.playerShare);
	}

	@PostMapping("redeem")
	@ResponseStatus(HttpStatus.CREATED)
	public void redeem(@RequestBody MarketRequest request) {
		// TODO validate args
		market.redeem(request.userId, request.amount, request.playerShare);
	}
}
