package com.openelo.market.common;

import java.time.Clock;
import java.util.Optional;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.auditing.DateTimeProvider;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

@Configuration
@EnableJpaAuditing(dateTimeProviderRef = PersistenceConfig.DATE_TIME_PROVIDER)
public class PersistenceConfig {

	static final String DATE_TIME_PROVIDER = "auditingDateTimeProvider";

	@Bean(DATE_TIME_PROVIDER)
	DateTimeProvider auditDateTimeProvider(Clock clock) {
		return () -> Optional.of(clock.instant());
	}
}
