package com.openelo.market.common;

import java.time.Instant;
import java.util.UUID;

import org.hibernate.annotations.UuidGenerator;
import org.hibernate.annotations.UuidGenerator.Style;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import jakarta.persistence.EntityListeners;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.MappedSuperclass;

@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class BaseEntity<T> {

	@jakarta.persistence.Id
	@GeneratedValue
	@UuidGenerator(style = Style.VERSION_7)
	private UUID id;

	@CreatedDate
	private Instant createdAt;

	protected BaseEntity() {

	}

	public com.openelo.market.common.Id<T> getId() {
		return new com.openelo.market.common.Id<>(id);
	}

	public Instant getCreatedAt() {
		return createdAt;
	}

}
