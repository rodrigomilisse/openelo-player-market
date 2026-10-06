package com.openelo.market.ledger.account;

import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AccountRepository extends JpaRepository<AAccount, UUID> {

}
