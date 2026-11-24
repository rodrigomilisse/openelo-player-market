package com.openelo.ingestion;

import java.time.Instant;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
class PingController {
	@GetMapping("/ping")
	Map<String, Object> ping() {
		return Map.of("service", "ingestion-service", "time", Instant.now(), "hello", "goodbye");
	}
}
