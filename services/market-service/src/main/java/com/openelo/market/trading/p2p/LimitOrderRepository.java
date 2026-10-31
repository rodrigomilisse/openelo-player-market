package com.openelo.market.trading.p2p;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

interface LimitOrderRepository extends JpaRepository<LimitOrder, UUID> {

	// held until the transaction ends
	@Query(value = "select 1 from pg_advisory_xact_lock(:key)", nativeQuery = true)
	int lockBook(long key);
}
