package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

// TODO weird naming
interface MarketTransactionRepository extends JpaRepository<ATransaction<?>, UUID> {

}
