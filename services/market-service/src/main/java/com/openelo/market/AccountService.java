package com.openelo.market;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.openelo.market.ledger.UserAccount;
import com.openelo.market.ledger.UserAccountRepository;

import jakarta.transaction.Transactional;

@Service
public class AccountService {

	@Autowired
	UserAccountRepository userAccounts;

	public AccountService(UserAccountRepository userAccountRepository) {
		this.userAccounts = userAccountRepository;
	}

	@Transactional
	public void createAccount(User user) {
		userAccounts.save(new UserAccount(user));
	}

}
