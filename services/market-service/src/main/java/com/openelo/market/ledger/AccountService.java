package com.openelo.market.ledger;

import org.springframework.stereotype.Service;

import com.openelo.market.common.Id;

import jakarta.transaction.Transactional;

@Service
public class AccountService {

	AccountRepository accountRepository;

	public AccountService(AccountRepository accountRepository) {
		this.accountRepository = accountRepository;
	}

	@Transactional
	public Id<IAccount> openAccount(boolean allowedNegative) {
		return accountRepository.save(new Account(allowedNegative)).getId();
	}

}
