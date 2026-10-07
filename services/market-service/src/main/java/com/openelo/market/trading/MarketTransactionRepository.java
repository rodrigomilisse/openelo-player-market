package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

interface MarketTransactionRepository extends JpaRepository<ATransaction<?>, UUID> {

}
