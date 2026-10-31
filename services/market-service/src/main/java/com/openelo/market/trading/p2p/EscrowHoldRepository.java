package com.openelo.market.trading.p2p;

import java.util.Optional;
import java.util.UUID;

import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;

interface EscrowHoldRepository extends Repository<EscrowHold, UUID> {

	@Query("""
			select min(h.level.limitPrice) from EscrowHold h
			where h.level.shareId = :shareId and h.level.side = :side
			  and h.level.limitPrice > :above and h.level.limitPrice <= :limitPrice""")
	Optional<Long> findLevelAbove(UUID shareId, Side side, long above, long limitPrice);

	@Query("""
			select max(h.level.limitPrice) from EscrowHold h
			where h.level.shareId = :shareId and h.level.side = :side
			  and h.level.limitPrice < :below and h.level.limitPrice >= :limitPrice""")
	Optional<Long> findLevelBelow(UUID shareId, Side side, long below, long limitPrice);
}
