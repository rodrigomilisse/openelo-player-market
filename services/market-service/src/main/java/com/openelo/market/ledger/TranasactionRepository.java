package com.openelo.market.ledger;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

public interface TranasactionRepository extends JpaRepository<ATransaction, UUID> {

}
