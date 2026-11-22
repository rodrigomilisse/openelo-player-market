package com.openelo.ingestion.match;

import java.time.LocalDate;
import java.util.List;

import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("matches")
class MatchController {

	private final MatchSource matchSource;

	MatchController(MatchSource matchSource) {
		this.matchSource = matchSource;
	}

	@GetMapping
	List<CompletedMatch> finished(
			@RequestParam String competition,
			@RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
			@RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
		return matchSource.finishedMatches(competition, from, to);
	}

	@GetMapping("{sourceMatchId}")
	ResponseEntity<CompletedMatch> one(@PathVariable String sourceMatchId) {
		return matchSource.match(sourceMatchId)
				.map(ResponseEntity::ok)
				.orElseGet(() -> ResponseEntity.notFound().build());
	}
}
