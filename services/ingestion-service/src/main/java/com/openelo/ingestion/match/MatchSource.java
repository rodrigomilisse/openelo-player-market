package com.openelo.ingestion.match;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * The provider-neutral port (ADR-0017 decision 5). Each provider gets one
 * adapter; the domain sees only CompletedMatch, never a provider's own shape.
 */
public interface MatchSource {

	List<CompletedMatch> finishedMatches(String competition, LocalDate from, LocalDate to);

	Optional<CompletedMatch> match(String sourceMatchId);
}
