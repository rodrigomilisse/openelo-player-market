package com.openelo.market.trading.p2p;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.user.IUser;

@RestController
@RequestMapping("p2p")
public class P2pVenueController {

	P2pVenue p2pVenue;

	P2pVenueController(P2pVenue p2pVenue) {
		this.p2pVenue = p2pVenue;
	}

	record PlaceRequest(Id<IUser> userId, Id<IAsset> playerShare, Side side, long shareAmount, long limitPrice) {
	}

	record CancelRequest(Id<IUser> userId) {
	}

	record OrderResponse(Id<LimitOrder> orderId) {
	}

	@PostMapping("orders")
	@ResponseStatus(HttpStatus.CREATED)
	public OrderResponse place(@RequestBody PlaceRequest request) {
		return new OrderResponse(p2pVenue.place(request.userId, request.playerShare, request.side,
				request.shareAmount, request.limitPrice));
	}

	@PostMapping("orders/{orderId}/cancel")
	public void cancel(@PathVariable UUID orderId, @RequestBody CancelRequest request) {
		p2pVenue.cancel(request.userId, new Id<>(orderId));
	}
}
