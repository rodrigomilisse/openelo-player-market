package com.openelo.market.user;

import java.time.Instant;

import com.openelo.market.common.Id;

public interface IUser {

	public Id<IUser> getId();

	public String getUsername();

	public Instant getCreatedAt();
}
