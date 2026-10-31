package com.openelo.market.trading.p2p;

import java.util.Optional;
import java.util.UUID;

import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;

interface EscrowHoldRepository extends Repository<EscrowHold, UUID> {

	@Query("""
			select min(h.limitPrice) from EscrowHold h
			where h.shareId = :shareId and h.side = :side
			  and h.limitPrice > :above and h.limitPrice <= :limitPrice""")
	Optional<Long> findLevelAbove(UUID shareId, Side side, long above, long limitPrice);

	@Query("""
			select max(h.limitPrice) from EscrowHold h
			where h.shareId = :shareId and h.side = :side
			  and h.limitPrice < :below and h.limitPrice >= :limitPrice""")
	Optional<Long> findLevelBelow(UUID shareId, Side side, long below, long limitPrice);
}
