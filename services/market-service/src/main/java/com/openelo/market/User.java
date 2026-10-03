package com.openelo.market;

import java.time.Instant;
import java.util.UUID;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "users")
public class User implements IUser {

	@Id
	private UUID id;

	private String username;

	private Instant createdAt;

	protected User() {

	}

	public User(String username) {
		this.username = username;
		this.id = UUID.randomUUID();
		this.createdAt = Instant.now();

	}

	@Override
	public UUID getId() {
		return id;
	}

	@Override
	public String getUsername() {
		return username;
	}

	@Override
	public Instant getCreatedAt() {
		return createdAt;
	}
}
