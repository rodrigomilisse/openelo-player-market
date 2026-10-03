package com.openelo.market;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.openelo.market.ledger.AAccount;

public interface AccountRepository extends JpaRepository<AAccount, UUID> {

}
