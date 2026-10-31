package com.openelo.market.trading.p2p;

import java.util.UUID;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import com.openelo.market.common.BaseEntity;
import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.trading.Platform;
import com.openelo.market.user.IUser;

import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Table;

@Entity
@Table(name = "limit_orders")
class LimitOrder extends BaseEntity<LimitOrder> {

	private UUID userId;

	private UUID shareId;

	@Enumerated(EnumType.STRING)
	@JdbcTypeCode(SqlTypes.NAMED_ENUM)
	private Side side;

	private long quantity;

	private long limitPrice;

	protected LimitOrder() {

	}

	LimitOrder(Id<IUser> userId, Id<IAsset> shareId, Side side, long quantity, long limitPrice) {
		this.userId = userId.value();
		this.shareId = shareId.value();
		this.side = side;
		this.quantity = quantity;
		this.limitPrice = limitPrice;
	}

	Id<IUser> getUserId() {
		return new Id<>(userId);
	}

	Id<IAsset> getShareId() {
		return new Id<>(shareId);
	}

	Side getSide() {
		return side;
	}

	long getQuantity() {
		return quantity;
	}

	long getLimitPrice() {
		return limitPrice;
	}

	Id<IAsset> lockedAsset(Platform platform) {
		return side == Side.BUY ? platform.getCreditsId() : getShareId();
	}

	long lockedAmount(long shareAmount) {
		return side == Side.BUY ? Math.multiplyExact(limitPrice, shareAmount) : shareAmount;
	}
}
