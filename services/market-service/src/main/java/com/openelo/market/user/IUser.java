package com.openelo.market.user;

import com.openelo.market.common.Recorded;

public interface IUser extends Recorded<IUser> {

	public String getUsername();
}
