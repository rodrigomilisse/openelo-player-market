package com.openelo.market.ledger.account;

import com.openelo.market.user.User;
import org.springframework.stereotype.Service;
import jakarta.transaction.Transactional;

@Service
public class AccountService {

	UserAccountRepository userAccounts;

	public AccountService(UserAccountRepository userAccountRepository) {
		this.userAccounts = userAccountRepository;
	}

	@Transactional
	public void createAccount(User user) {
		userAccounts.save(new UserAccount(user));
	}

}
