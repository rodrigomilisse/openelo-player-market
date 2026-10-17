package com.openelo.market.ledger;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface TransactionRepository extends JpaRepository<Transaction, UUID> {

	@Query("SELECT COALESCE(SUM(p.amount), 0) FROM ledger_transactions t JOIN postings p WHERE p.accountId = :accountId AND p.assetId = :assetId")
	public long getBalance(UUID accountId, UUID assetId);
}
