package com.openelo.ingestion.footballdata;

import java.time.Instant;
import java.util.List;

/**
 * The slices of football-data.org's v4 JSON this adapter reads. Unknown fields
 * are ignored (Spring Boot's Jackson default), so only the facts the formula
 * needs are modelled.
 */
final class FootballDataResponses {

	private FootballDataResponses() {
	}

	record MatchesResponse(List<Match> matches) {
	}

	record Match(
			long id,
			Instant utcDate,
			String status,
			String stage,
			Competition competition,
			Season season,
			Team homeTeam,
			Team awayTeam,
			Score score) {
	}

	record Competition(long id, String code, String name) {
	}

	record Season(String startDate) {
	}

	record Team(Long id, String name) {
	}

	record Score(String winner, String duration, Goals fullTime) {
	}

	record Goals(Integer home, Integer away) {
	}
}
