package com.openelo.market.trading.p2p;

import java.util.UUID;

import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.Synchronize;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.MapsId;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;

// maps the open_orders view, so it is never written
@Entity
@Immutable
@Table(name = "open_orders")
@Synchronize({ "limit_orders", "trades", "market_transactions", "postings", "order_cancellations" })
class OpenOrder {

	@Id
	private UUID orderId;

	@OneToOne(optional = false)
	@MapsId
	@JoinColumn(name = "order_id")
	private LimitOrder order;

	private long remaining;

	protected OpenOrder() {
	}

	LimitOrder getOrder() {
		return order;
	}

	long getRemaining() {
		return remaining;
	}
}
