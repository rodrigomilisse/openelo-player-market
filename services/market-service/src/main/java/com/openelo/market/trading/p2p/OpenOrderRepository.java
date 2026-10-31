package com.openelo.market.trading.p2p;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.data.domain.Limit;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;

interface OpenOrderRepository extends Repository<OpenOrder, UUID> {

	Optional<OpenOrder> findById(UUID orderId);

	// Reads from the level's frontier, its latest order that has been a maker:
	// everything before it is closed (ADR-0012). Ordering by id after created_at
	// keeps matching deterministic when timestamps tie; the share lock makes ties
	// rare, but a frozen dev clock stamps every order alike.
	@Query("""
			select o from OpenOrder o join EscrowHold h on h.orderId = o.orderId
			where h.shareId = :shareId and h.side = :side and h.limitPrice = :price
			  and h.orderCreatedAt >= coalesce((
			      select f.orderCreatedAt from EscrowHold f
			      where f.shareId = :shareId and f.side = :side and f.limitPrice = :price
			        and exists (select t.id from Trade t where t.makerOrderId = f.orderId)
			      order by f.orderCreatedAt desc
			      limit 1),
			    :beforeEveryOrder)
			order by h.orderCreatedAt, h.orderId""")
	List<OpenOrder> findOpenAt(UUID shareId, Side side, long price, Instant beforeEveryOrder, Limit limit);
}
