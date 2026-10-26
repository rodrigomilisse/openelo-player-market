package com.openelo.market.pricing;

import java.util.List;
import java.util.function.ToLongFunction;

import org.springframework.stereotype.Service;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

@Service
public final class Quoter {

	private final ShareService shareService;

	private final List<QuoteComponent> components;

	Quoter(ShareService shareService, List<QuoteComponent> components) {
		this.shareService = shareService;
		this.components = components;
	}

	public Quote quoteMint(Id<IAsset> share, long shareAmount) {
		requireNatural(shareAmount);
		long backing = total(QuoteRole.BACKING, component -> component.walkUp(share, shareAmount));
		long revenue = total(QuoteRole.REVENUE, component -> component.walkUp(share, shareAmount));
		return new Quote(backing, revenue);
	}

	public long quoteRedeem(Id<IAsset> share, long shareAmount) {
		requireNatural(shareAmount);
		requireAvailable(share, shareAmount);
		return total(QuoteRole.BACKING, component -> component.walkDown(share, shareAmount));
	}

	private long total(QuoteRole role, ToLongFunction<QuoteComponent> price) {
		return components.stream().filter(component -> component.role() == role).mapToLong(price)
				.reduce(0L, Math::addExact);
	}

	private void requireAvailable(Id<IAsset> share, long shareAmount) {
		long supply = shareService.getSupply(share);
		if (shareAmount > supply) {
			throw new IllegalArgumentException("Cannot redeem " + shareAmount + " shares, only " + supply + " exist");
		}
	}

	private void requireNatural(long shareAmount) {
		if (shareAmount < 0) {
			throw new IllegalArgumentException("Share amount cannot be negative, was " + shareAmount);
		}
	}
}
