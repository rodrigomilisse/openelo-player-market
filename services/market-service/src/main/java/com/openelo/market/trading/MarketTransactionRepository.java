package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

// TODO weird naming
public interface MarketTransactionRepository extends JpaRepository<ATransaction<?>, UUID> {

	@Query(value = "select 1 from pg_advisory_xact_lock(hashtextextended(cast(:shareId as text), 0))", nativeQuery = true)
	int lockShare(UUID shareId);
}
