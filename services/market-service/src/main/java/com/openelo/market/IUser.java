package com.openelo.market;

import java.time.Instant;
import java.util.UUID;

public interface IUser {

	public UUID getId();

	public String getUsername();

	public Instant getCreatedAt();
}
