package com.openelo.market.trading.p2p;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

interface LimitOrderRepository extends JpaRepository<LimitOrder, UUID> {
}
