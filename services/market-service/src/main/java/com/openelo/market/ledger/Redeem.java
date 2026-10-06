package com.openelo.market.ledger;

import com.openelo.market.ledger.account.PlatformAccount;
import com.openelo.market.ledger.account.UserAccount;
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

	protected Redeem() {

	}

	public Redeem(UserAccount userAccount, long shareAmount, AssetId playerShare, long pricePerShare) {

		super(UUID.randomUUID());
		this.userAccount = userAccount;

		this.postings = new ArrayList<>(4);

		long creditAmount = Math.multiplyExact(shareAmount, pricePerShare);

		Posting removeSharesFromUser = debit(userAccount, shareAmount, playerShare);
		Posting removeCreditsFromPlatform = debit(PlatformAccount.ID, creditAmount, AssetId.CREDITS);
		Posting addSharesToPlatform = credit(PlatformAccount.ID, shareAmount, playerShare);
		Posting addCreditsToUser = credit(userAccount, creditAmount, AssetId.CREDITS);

		this.postings.add(removeSharesFromUser);
		this.postings.add(removeCreditsFromPlatform);
		this.postings.add(addSharesToPlatform);
		this.postings.add(addCreditsToUser);

	}

	public UserAccount getUserAccount() {
		return this.userAccount;
	}
}
