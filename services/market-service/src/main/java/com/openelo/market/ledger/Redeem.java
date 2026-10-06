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
@Table(name = "redeems")
public class Redeem extends ATransaction {

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "user_account")
	private UserAccount userAccount;

	private static final IAccount platformAccount = new PlatformAccount(new UUID(0, 0));

	private static final UUID credits = new UUID(0, 0);

	protected Redeem() {

	}

	public Redeem(UserAccount userAccount, long shareAmount, UUID playerShare, long pricePerShare) {

		this.id = UUID.randomUUID();
		this.userAccount = userAccount;

		this.createdAt = Instant.now();

		this.postings = new ArrayList<>(4);

		long creditAmount = Math.multiplyExact(shareAmount, pricePerShare);

		Posting removeSharesFromUser = debit(userAccount, shareAmount, playerShare);
		Posting removeCreditsFromPlatform = debit(platformAccount, creditAmount, credits);
		Posting addSharesToPlatform = credit(platformAccount, shareAmount, playerShare);
		Posting addCreditsToUser = credit(userAccount, creditAmount, credits);

		this.postings.add(removeSharesFromUser);
		this.postings.add(removeCreditsFromPlatform);
		this.postings.add(addSharesToPlatform);
		this.postings.add(addCreditsToUser);

	}

	public UserAccount getUserAccount() {
		return this.userAccount;
	}
}
