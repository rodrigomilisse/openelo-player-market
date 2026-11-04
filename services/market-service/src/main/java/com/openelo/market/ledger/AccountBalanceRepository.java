package com.openelo.market.ledger;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.data.repository.Repository;

public interface AccountBalanceRepository extends Repository<AccountBalance, AccountBalanceKey> {

	List<AccountBalance> findByIdAccountId(UUID accountId);

	Optional<AccountBalance> findById(AccountBalanceKey id);
}
