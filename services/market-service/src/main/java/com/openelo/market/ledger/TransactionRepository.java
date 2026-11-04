package com.openelo.market.ledger;

import java.time.Instant;
import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface TransactionRepository extends JpaRepository<Transaction, UUID> {

	@Query("""
			select coalesce(sum(p.amount), 0)
			from Transaction t join t.postings p
			where p.fromAccountId = :accountId
			  and p.assetId = :assetId
			  and t.createdAt > :since""")
	long getOutflow(UUID accountId, UUID assetId, Instant since);
}
