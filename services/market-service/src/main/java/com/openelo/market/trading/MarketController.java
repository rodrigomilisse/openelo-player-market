package com.openelo.market.trading;

import com.openelo.market.pricing.ShareService;
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

	ShareService shareService;

	MarketController(Market market, ShareService shareService, UserRepository userRepository, WalletRepository walletRepository) {
		this.market = market;
		this.shareService = shareService;
	}

	record MarketRequest(Id<IUser> userId, long amount, Id<IAsset> playerShare) {
	}

	record ShareResponse(Id<IAsset> shareId) {
	}

	@PostMapping("shares")
	@ResponseStatus(HttpStatus.CREATED)
	public ShareResponse list() {
		return new ShareResponse(shareService.listShare());
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
