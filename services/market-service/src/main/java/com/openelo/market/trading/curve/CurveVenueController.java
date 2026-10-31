package com.openelo.market.trading.curve;

import com.openelo.market.pricing.ShareService;
import com.openelo.market.user.IUser;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

@RestController
@RequestMapping("curve")
public class CurveVenueController {

	CurveVenue curveVenue;

	ShareService shareService;

	CurveVenueController(CurveVenue curveVenue, ShareService shareService) {
		this.curveVenue = curveVenue;
		this.shareService = shareService;
	}

	record CurveRequest(Id<IUser> userId, long shareAmount, Id<IAsset> playerShare) {
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
	public void mint(@RequestBody CurveRequest request) {
		// TODO validate args
		curveVenue.mint(request.userId, request.shareAmount, request.playerShare);
	}

	@PostMapping("redeem")
	@ResponseStatus(HttpStatus.CREATED)
	public void redeem(@RequestBody CurveRequest request) {
		// TODO validate args
		curveVenue.redeem(request.userId, request.shareAmount, request.playerShare);
	}
}
