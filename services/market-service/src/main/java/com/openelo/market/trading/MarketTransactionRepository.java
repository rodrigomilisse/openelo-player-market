package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

// TODO weird naming
public interface MarketTransactionRepository extends JpaRepository<ATransaction<?>, UUID> {

}
