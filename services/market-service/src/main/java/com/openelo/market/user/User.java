package com.openelo.market.user;

import com.openelo.market.common.BaseEntity;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "users")
public class User extends BaseEntity<IUser> implements IUser {

	private String username;

	protected User() {

	}

	public User(String username) {
		this.username = username;
	}

	@Override
	public String getUsername() {
		return username;
	}
}
