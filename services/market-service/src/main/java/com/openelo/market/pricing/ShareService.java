package com.openelo.market.pricing;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Ledger;

import jakarta.transaction.Transactional;

@Service
public class ShareService {

	private static final Object SUPPLIES = new Object();

	private final Ledger ledger;

	public ShareService(Ledger ledger) {
		this.ledger = ledger;
	}

	// the share takes the id of the account it opens, so finding a share's pool
	// needs no lookup
	@Transactional
	public Id<IAsset> listShare() {
		return new Id<>(ledger.openAccount().value());
	}

	public Id<IAccount> getPoolAccountId(Id<IAsset> share) {
		return new Id<>(share.value());
	}

	// TODO revisit whether remembering the supply per transaction is the best way to share it between
	// the quote components (see the pricing README)
	// Read once per transaction: the components of a quote all ask for it, and a
	// mint or redeem reads
	// the supply before it posts. A flow that posts and then reads again would see
	// the old value.
	public long getSupply(Id<IAsset> share) {
		return suppliesInThisTransaction().computeIfAbsent(share, this::readSupply);
	}

	// only mints move shares out of the pool
	public long getMintedSince(Id<IAsset> share, Instant since) {
		Id<IAccount> pool = getPoolAccountId(share);
		return ledger.getOutflow(pool, share, since);
	}

	// shares are issued from the pool, so the supply is minus its balance
	private long readSupply(Id<IAsset> share) {
		Id<IAccount> pool = getPoolAccountId(share);
		long poolBalance = ledger.getBalance(pool, share);
		return Math.negateExact(poolBalance);
	}

	@SuppressWarnings("unchecked")
	private Map<Id<IAsset>, Long> suppliesInThisTransaction() {
		if (!TransactionSynchronizationManager.hasResource(SUPPLIES)) {
			TransactionSynchronizationManager.bindResource(SUPPLIES, new HashMap<Id<IAsset>, Long>());
			TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
				@Override
				public void afterCompletion(int status) {
					TransactionSynchronizationManager.unbindResource(SUPPLIES);
				}
			});
		}
		return (Map<Id<IAsset>, Long>) TransactionSynchronizationManager.getResource(SUPPLIES);
	}
}
