package com.openelo.market.ledger;

import java.time.Instant;
import java.util.ArrayList;
import java.util.UUID;

import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "mints")
public class Mint extends ATransaction {

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "user_account")
	private UserAccount userAccount;

	private static final IAccount platformAccount = new PlatformAccount(new UUID(0, 0));

	private static final UUID credits = new UUID(0, 0);

	// private long shareAmount;

	// private UUID playerShare;

	// private long pricePerShare;

	private Posting debit(IAccount account, long amount, UUID asset) {
		return new Posting(account.getId(), Math.negateExact(amount), asset);
	}

	private Posting credit(IAccount account, long amount, UUID asset) {
		return new Posting(account.getId(), amount, asset);
	}

	protected Mint() {

	}

	public Mint(UserAccount userAccount, long shareAmount, UUID playerShare, long pricePerShare) {

		this.id = UUID.randomUUID();
		this.userAccount = userAccount;
		// this.shareAmount = shareAmount;
		// this.playerShare = playerShare;
		// this.pricePerShare = pricePerShare;
		this.createdAt = Instant.now();

		this.postings = new ArrayList<>(4);

		long creditAmount = Math.multiplyExact(shareAmount, pricePerShare);

		Posting removeCreditsFromUser = debit(userAccount, creditAmount, credits);
		Posting removeFromShareFromPlatform = debit(platformAccount, shareAmount, playerShare);
		Posting addCreditsToPlatform = credit(platformAccount, creditAmount, credits);
		Posting addSharesToUser = credit(userAccount, shareAmount, playerShare);

		this.postings.add(removeCreditsFromUser);
		this.postings.add(removeFromShareFromPlatform);
		this.postings.add(addCreditsToPlatform);
		this.postings.add(addSharesToUser);
	}

	public UserAccount getUserAccount() {
		return this.userAccount;
	}

	// public long getShareAmount() {
	// return this.shareAmount;
	// }
	//
	// public UUID getPlayerShare() {
	// return this.playerShare;
	// }
	//
	// public long pricePerShare() {
	// return this.pricePerShare;
	// }
}
