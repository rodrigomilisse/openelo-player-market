package com.openelo.market.common;

import java.nio.file.Path;
import java.time.Clock;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

// openelo.clock.mode picks the Clock every time-dependent bean receives:
// system (default) is real UTC time, manual only moves when told to (ClockController)
@Configuration
public class TimeConfig {

	@Bean
	@ConditionalOnProperty(name = "openelo.clock.mode", havingValue = "system", matchIfMissing = true)
	Clock clock() {
		return Clock.systemUTC();
	}

	@Bean
	@ConditionalOnProperty(name = "openelo.clock.mode", havingValue = "manual")
	ManualClock manualClock(@Value("${openelo.clock.file:.manual-clock}") String file) {
		return ManualClock.load(Path.of(file));
	}
}
