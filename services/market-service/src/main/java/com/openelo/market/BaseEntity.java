package com.openelo.market;

import java.time.Instant;
import java.util.UUID;
import org.springframework.data.domain.Persistable;
import jakarta.persistence.Transient;
import jakarta.persistence.Id;
import jakarta.persistence.MappedSuperclass;
import jakarta.persistence.PostLoad;
import jakarta.persistence.PostPersist;

@MappedSuperclass
public abstract class BaseEntity implements Persistable<UUID> {

	@Id
	private UUID id;

	private Instant createdAt;

	@Transient
	boolean isNew;

	protected BaseEntity() {

	}

	protected BaseEntity(UUID id) {
		this.id = id;
		this.createdAt = Instant.now();
	}

	@Override
	public UUID getId() {
		return id;
	}

	public Instant getCreatedAt() {
		return createdAt;
	}

	@Override
	public boolean isNew() {
		return isNew;
	}

	@PostPersist
	@PostLoad
	private void markNotNew() {
		isNew = false;
	}
}
