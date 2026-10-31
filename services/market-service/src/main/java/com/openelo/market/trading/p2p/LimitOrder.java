package com.openelo.market.trading.p2p;

import java.util.UUID;

import com.openelo.market.common.BaseEntity;
import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.trading.Platform;
import com.openelo.market.user.IUser;

import jakarta.persistence.Embedded;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "limit_orders")
class LimitOrder extends BaseEntity<LimitOrder> {

	private UUID userId;

	@Embedded
	private Level level;

	private long quantity;

	protected LimitOrder() {

	}

	LimitOrder(Id<IUser> userId, Id<IAsset> shareId, Side side, long quantity, long limitPrice) {
		this.userId = userId.value();
		this.level = new Level(shareId.value(), side, limitPrice);
		this.quantity = quantity;
	}

	Id<IUser> getUserId() {
		return new Id<>(userId);
	}

	Level getLevel() {
		return level;
	}

	Id<IAsset> getShareId() {
		return new Id<>(level.shareId());
	}

	Side getSide() {
		return level.side();
	}

	long getQuantity() {
		return quantity;
	}

	long getLimitPrice() {
		return level.limitPrice();
	}

	Id<IAsset> lockedAsset(Platform platform) {
		return getSide() == Side.BUY ? platform.getCreditsId() : getShareId();
	}

	long lockedAmount(long shareAmount) {
		return getSide() == Side.BUY ? Math.multiplyExact(getLimitPrice(), shareAmount) : shareAmount;
	}
}
