package com.openelo.market.trading.p2p;

import java.time.Instant;
import java.time.LocalDate;
import java.time.Month;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.data.domain.Limit;
import org.springframework.stereotype.Component;

@Component
class OrderBook {

	private static final long BELOW_EVERY_PRICE = 0;

	private static final long ABOVE_EVERY_PRICE = Long.MAX_VALUE;

	private static final LocalDate FIRST_OF_JANUARY_YEAR_ONE = LocalDate.of(1, Month.JANUARY, 1);

	private static final Instant BEFORE_EVERY_ORDER = FIRST_OF_JANUARY_YEAR_ONE.atStartOfDay(ZoneOffset.UTC).toInstant();

	private final EscrowHoldRepository escrowHoldRepository;

	private final OpenOrderRepository openOrderRepository;

	OrderBook(EscrowHoldRepository escrowHoldRepository, OpenOrderRepository openOrderRepository) {
		this.escrowHoldRepository = escrowHoldRepository;
		this.openOrderRepository = openOrderRepository;
	}

	// a buy meets the cheapest sells first, a sell the dearest buys
	Optional<Long> findFirstLevel(LimitOrder taker) {
		long beyondEveryLevel = taker.getSide() == Side.BUY ? BELOW_EVERY_PRICE : ABOVE_EVERY_PRICE;
		return findNextLevel(taker, beyondEveryLevel);
	}

	Optional<Long> findNextLevel(LimitOrder taker, long price) {
		UUID share = taker.getShareId().value();
		if (taker.getSide() == Side.BUY) {
			return escrowHoldRepository.findLevelAbove(share, Side.SELL, price, taker.getLimitPrice());
		}
		return escrowHoldRepository.findLevelBelow(share, Side.BUY, price, taker.getLimitPrice());
	}

	// each open order has a share left, so shareAmount bounds how many are needed
	List<OpenOrder> findOpenAt(LimitOrder taker, long price, long shareAmount) {
		Side restingSide = taker.getSide().opposite();
		Limit limit = Limit.of(Math.toIntExact(shareAmount));
		return openOrderRepository.findOpenAt(taker.getShareId().value(), restingSide, price, BEFORE_EVERY_ORDER,
				limit);
	}
}
