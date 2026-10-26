package com.openelo.market.pricing;

// backing stays in the share's pool and pays redeems; revenue goes to the platform
public record Quote(long backing, long revenue) {
}
