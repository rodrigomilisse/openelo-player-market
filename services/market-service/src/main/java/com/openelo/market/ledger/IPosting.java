package com.openelo.market.ledger;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

public interface IPosting {

	Id<IAccount> getFromAccountId();

	Id<IAccount> getToAccountId();

	long getAmount();

	Id<IAsset> getAssetId();

}
