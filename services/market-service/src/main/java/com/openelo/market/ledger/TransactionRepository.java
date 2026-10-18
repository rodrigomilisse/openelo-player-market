package com.openelo.market.ledger;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface TransactionRepository extends JpaRepository<Transaction, UUID> {
	// Native so it reads postings directly. Postings are an @ElementCollection, not
	// an entity, so JPQL can only reach them through their owning transaction,
	// which joins ledger_transactions for nothing.
	@Query(value = """
			SELECT COALESCE(SUM(CASE WHEN to_account_id = :accountId THEN amount ELSE -amount END), 0)
			FROM postings
			WHERE asset_id = :assetId
			  AND (to_account_id = :accountId OR from_account_id = :accountId)
			""", nativeQuery = true)
	long getBalance(UUID accountId, UUID assetId);
}
