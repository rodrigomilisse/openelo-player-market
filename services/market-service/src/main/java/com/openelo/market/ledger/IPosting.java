package com.openelo.market.ledger;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

public interface IPosting {

	Id<IAccount> getAccountId();

	long getAmount();

	Id<IAsset> getAssetId();

}
