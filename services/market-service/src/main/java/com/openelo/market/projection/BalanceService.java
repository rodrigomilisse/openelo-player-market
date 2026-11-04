package com.openelo.market.projection;

import java.util.HashMap;
import java.util.Map;

import org.springframework.data.redis.RedisConnectionFailureException;
import org.springframework.data.redis.core.HashOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.Balances;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.trading.WalletService;
import com.openelo.market.user.IUser;

@Service
class BalanceService {

	private final StringRedisTemplate redis;

	private final Ledger ledger;

	private final WalletService walletService;

	BalanceService(StringRedisTemplate redis, Ledger ledger, WalletService walletService) {
		this.redis = redis;
		this.ledger = ledger;
		this.walletService = walletService;
	}

	// TODO when ADR-0015 is applied: the accounts come from the newest wallet rows,
	// read through the wallet:{userId} cache the projector updates on rollover
	Balances getAvailable(Id<IUser> userId) {
		return getBalances(walletService.getAccount(userId));
	}

	Balances getEscrowed(Id<IUser> userId) {
		return getBalances(walletService.getEscrowAccount(userId));
	}

	private Balances getBalances(Id<IAccount> accountId) {
		if (isProjectionReady()) {
			return readProjection(accountId);
		}
		return ledger.getBalances(accountId);
	}

	private boolean isProjectionReady() {
		try {
			return Boolean.TRUE.equals(redis.hasKey(ProjectionKeys.READY));
		} catch (RedisConnectionFailureException e) {
			return false;
		}
	}

	private Balances readProjection(Id<IAccount> accountId) {
		HashOperations<String, String, String> hashes = redis.opsForHash();
		Map<Id<IAsset>, Long> balances = new HashMap<>();
		hashes.entries(BalanceHash.key(accountId))
				.forEach((field, value) -> balances.put(BalanceHash.toAsset(field), BalanceHash.toBalance(value)));
		return new Balances(balances);
	}
}
