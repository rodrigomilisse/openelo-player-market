package com.openelo.market.common;

import java.time.Instant;

public interface Recorded<T> {

	public Id<T> getId();

	public Instant getCreatedAt();

}
