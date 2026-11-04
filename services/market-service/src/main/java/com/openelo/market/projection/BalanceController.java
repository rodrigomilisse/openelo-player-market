package com.openelo.market.projection;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.Balances;
import com.openelo.market.user.IUser;

@RestController
@RequestMapping("users")
class BalanceController {

	private final BalanceService balanceService;

	BalanceController(BalanceService balanceService) {
		this.balanceService = balanceService;
	}

	record BalancesResponse(Map<Id<IAsset>, Long> available, Map<Id<IAsset>, Long> escrowed) {
	}

	@GetMapping("{userId}/balances")
	BalancesResponse balances(@PathVariable UUID userId) {
		Id<IUser> user = new Id<>(userId);
		return new BalancesResponse(toResponse(balanceService.getAvailable(user)),
				toResponse(balanceService.getEscrowed(user)));
	}

	private Map<Id<IAsset>, Long> toResponse(Balances balances) {
		Map<Id<IAsset>, Long> response = new HashMap<>();
		balances.forEach((asset, balance) -> response.put(asset, balance));
		return response;
	}
}
