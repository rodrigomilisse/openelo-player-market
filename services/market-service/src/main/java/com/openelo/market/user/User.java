package com.openelo.market.user;

import java.util.UUID;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import com.openelo.market.BaseEntity;

@Entity
@Table(name = "users")
public class User extends BaseEntity implements IUser {

	private String username;

	protected User() {

	}

	public User(String username) {
		super(UUID.randomUUID());
		this.username = username;
	}

	@Override
	public String getUsername() {
		return username;
	}
}
