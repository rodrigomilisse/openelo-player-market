package com.openelo.market.trading;

import com.openelo.market.common.BaseEntity;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IPosting;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.ITransaction;

import java.util.List;
import java.util.UUID;
import jakarta.persistence.Entity;
import jakarta.persistence.Inheritance;
import jakarta.persistence.InheritanceType;
import jakarta.persistence.Table;
import jakarta.persistence.Transient;

@Entity // TODO holds no real data, not even pk
@Table(name = "market_transactions")
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class ATransaction<T> extends BaseEntity<T> implements ITransaction {

	@Transient
	protected List<IPosting> postings;

	UUID ledgerTransactionId;

	protected ATransaction() {

	}

	@Override
	public Iterable<IPosting> getPostings() {
		return postings;
	}

	public void setLedgerTransactionId(Id<IRecordedTransaction> recordedtransactionId) {
		this.ledgerTransactionId = recordedtransactionId.value();
	}

}
