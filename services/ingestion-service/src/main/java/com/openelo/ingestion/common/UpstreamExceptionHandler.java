package com.openelo.ingestion.common;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.RestClientResponseException;

/**
 * Turns a failed upstream call (bad or missing token is 403, rate limit is 429)
 * into a clean 502 the caller can read, instead of a stack trace.
 */
@RestControllerAdvice
class UpstreamExceptionHandler {

	@ExceptionHandler(RestClientResponseException.class)
	ResponseEntity<Map<String, Object>> upstream(RestClientResponseException exception) {
		return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of(
				"error", "football-data.org call failed",
				"upstreamStatus", exception.getStatusCode().value(),
				"upstreamBody", exception.getResponseBodyAsString()));
	}
}
