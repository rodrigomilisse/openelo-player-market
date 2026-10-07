package com.openelo.market.trading;

import org.springframework.stereotype.Service;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.user.IUser;
import com.openelo.market.user.User;
import com.openelo.market.user.UserRepository;

import jakarta.transaction.Transactional;

@Service
class SignUp {

	private static final boolean ALLOWED_NEGATIVE = false;

	private final UserRepository users;

	private final WalletRepository wallets;

	private final Ledger ledger;

	SignUp(UserRepository users, WalletRepository wallets, Ledger ledger) {
		this.users = users;
		this.wallets = wallets;
		this.ledger = ledger;
	}

	// user, ledger account and the wallet linking them commit together or not at all
	@Transactional
	public Id<IUser> signUp(String username) {
		User user = users.save(new User(username));
		Id<IAccount> account = ledger.openAccount(ALLOWED_NEGATIVE);
		wallets.save(new Wallet(user.getId(), account));
		return user.getId();
	}
}
