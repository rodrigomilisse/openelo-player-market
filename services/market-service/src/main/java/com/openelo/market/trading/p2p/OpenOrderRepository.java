package com.openelo.market.trading.p2p;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.data.domain.Limit;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;

interface OpenOrderRepository extends Repository<OpenOrder, UUID> {

	Optional<OpenOrder> findById(UUID orderId);

	// the book's matching order: best price first, then earliest
	@Query("""
			select o from OpenOrder o
			where o.order.shareId = :shareId and o.order.side = com.openelo.market.trading.p2p.Side.SELL
			  and o.order.limitPrice <= :price
			order by o.order.limitPrice asc, o.order.createdAt asc, o.orderId asc""")
	List<OpenOrder> findSellsUpTo(UUID shareId, long price, Limit limit);

	@Query("""
			select o from OpenOrder o
			where o.order.shareId = :shareId and o.order.side = com.openelo.market.trading.p2p.Side.BUY
			  and o.order.limitPrice >= :price
			order by o.order.limitPrice desc, o.order.createdAt asc, o.orderId asc""")
	List<OpenOrder> findBuysFrom(UUID shareId, long price, Limit limit);
}
