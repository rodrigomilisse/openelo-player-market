package com.openelo.market.pricing;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

// the part of a mint's cost (walkUp) or a redeem's proceeds (walkDown) that one rule decides
interface QuoteComponent {

	long walkUp(Id<IAsset> share, long shareAmount);

	long walkDown(Id<IAsset> share, long shareAmount);
}
