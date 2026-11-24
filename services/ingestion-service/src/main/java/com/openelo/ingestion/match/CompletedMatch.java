package com.openelo.ingestion.match;

import java.time.Instant;
import java.util.List;

/**
 * The match.completed v1 event, as ADR-0017 decision 7 specifies it: only what
 * the rating formula reads, plus what identifies, orders and corrects a match.
 * Optional facts are empty lists, never nullable fields.
 */
public record CompletedMatch(
		int schemaVersion,
		String eventId,
		MatchRef match,
		int matchVersion,
		Instant knownAt,
		Instant kickOff,
		Competition competition,
		Stage stage,
		Venue venue,
		TeamRef home,
		TeamRef away,
		Result result,
		List<MatchRef> secondLegOf,
		List<Corners> corners,
		List<PlayerLine> players) {

	public record MatchRef(String source, String sourceMatchId) {
	}

	public record Competition(String sourceCompetitionId, int season, boolean national) {
	}

	public record TeamRef(String sourceTeamId) {
	}

	public record Result(ResultKind kind, int homeGoals, int awayGoals, boolean extraTime, boolean shootout) {
	}

	public record Corners(int home, int away) {
	}

	public record PlayerLine(String sourcePlayerId, Side side, boolean started, int minutes) {
	}
}
