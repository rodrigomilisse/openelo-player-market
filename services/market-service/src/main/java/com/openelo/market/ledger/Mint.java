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
@Table(name = "mints")
public class Mint extends ATransaction {

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "user_account")
	private UserAccount userAccount;

	protected Mint() {

	}

	public Mint(UserAccount userAccount, long shareAmount, AssetId playerShare, long pricePerShare) {

		super(UUID.randomUUID());

		this.userAccount = userAccount;
		this.postings = new ArrayList<>(4);

		long creditAmount = Math.multiplyExact(shareAmount, pricePerShare);

		Posting removeCreditsFromUser = debit(userAccount, creditAmount, AssetId.CREDITS);
		Posting removeFromShareFromPlatform = debit(PlatformAccount.ID, shareAmount, playerShare);
		Posting addCreditsToPlatform = credit(PlatformAccount.ID, creditAmount, AssetId.CREDITS);
		Posting addSharesToUser = credit(userAccount, shareAmount, playerShare);

		this.postings.add(removeCreditsFromUser);
		this.postings.add(removeFromShareFromPlatform);
		this.postings.add(addCreditsToPlatform);
		this.postings.add(addSharesToUser);
	}

	public UserAccount getUserAccount() {
		return this.userAccount;
	}
}
