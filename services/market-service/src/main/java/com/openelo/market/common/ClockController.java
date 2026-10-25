package com.openelo.market.common;

import java.time.Instant;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("dev/clock")
@ConditionalOnProperty(name = "openelo.clock.mode", havingValue = "manual")
class ClockController {

	private static final Logger log = LoggerFactory.getLogger(ClockController.class);

	private final ManualClock clock;

	ClockController(ManualClock clock) {
		this.clock = clock;
	}

	record ClockRequest(String command, boolean force) {
	}

	record ClockResponse(Instant previous, Instant now, String warning) {
	}

	record ClockError(String error) {
	}

	@GetMapping
	ClockResponse get() {
		Instant now = clock.instant();
		return new ClockResponse(now, now, null);
	}

	@PostMapping
	ResponseEntity<?> move(@RequestBody ClockRequest request) {
		Instant previous = clock.instant();
		Instant target;
		try {
			target = ClockCommands.apply(request.command(), previous);
		} catch (IllegalArgumentException e) {
			return ResponseEntity.badRequest().body(new ClockError(e.getMessage()));
		}

		if (!target.isBefore(previous)) {
			clock.set(target);
			return ResponseEntity.ok(new ClockResponse(previous, target, null));
		}

		// going back makes everything recorded after the target look like it happens
		// in the future, which changes time-based pricing (e.g. heat decay) from then on
		String warning = "Time moved backwards from " + previous + " to " + target
				+ ". Records created after " + target
				+ " now lie in the future, which changes pricing computed from them.";
		if (!request.force()) {
			return ResponseEntity.status(HttpStatus.CONFLICT)
					.body(new ClockError("Refused. " + warning + " Resend with force to do it anyway."));
		}
		clock.set(target);
		log.warn(warning);
		return ResponseEntity.ok(new ClockResponse(previous, target, warning));
	}
}
