package com.openelo.market.trading;

import org.springframework.stereotype.Service;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.user.IUser;

@Service
public class WalletService {

	private final WalletRepository walletRepository;

	WalletService(WalletRepository walletRepository) {
		this.walletRepository = walletRepository;
	}

	public Id<IAccount> getAccount(Id<IUser> userId) {
		return getWallet(userId).getAccountId();
	}

	public Id<IAccount> getEscrowAccount(Id<IUser> userId) {
		return getWallet(userId).getEscrowAccountId();
	}

	private Wallet getWallet(Id<IUser> userId) {
		return walletRepository.findByUserId(userId.value()).orElseThrow();
	}
}
