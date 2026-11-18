package com.openelo.ingestion.footballdata;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.openelo.ingestion.match.CompletedMatch;
import com.openelo.ingestion.match.CompletedMatch.Competition;
import com.openelo.ingestion.match.CompletedMatch.MatchRef;
import com.openelo.ingestion.match.CompletedMatch.Result;
import com.openelo.ingestion.match.CompletedMatch.TeamRef;
import com.openelo.ingestion.match.MatchSource;
import com.openelo.ingestion.match.ResultKind;
import com.openelo.ingestion.match.Stage;
import com.openelo.ingestion.match.Venue;
import com.openelo.ingestion.footballdata.FootballDataResponses.Match;
import com.openelo.ingestion.footballdata.FootballDataResponses.MatchesResponse;

/**
 * Adapter over football-data.org's v4 API. The free tier carries results and
 * fixtures but no line-ups, so {@code players} and {@code corners} come out
 * empty; the rating formula falls back to the result alone, as it does in
 * research for matches without that data.
 */
@Component
public class FootballDataMatchSource implements MatchSource {

	private static final String SOURCE = "FOOTBALL_DATA_ORG";

	private final RestClient restClient;

	FootballDataMatchSource(RestClient footballDataRestClient) {
		this.restClient = footballDataRestClient;
	}

	@Override
	public List<CompletedMatch> finishedMatches(String competition, LocalDate from, LocalDate to) {
		MatchesResponse response = restClient.get()
				.uri(builder -> builder.path("/competitions/{competition}/matches")
						.queryParam("status", "FINISHED")
						.queryParam("dateFrom", from)
						.queryParam("dateTo", to)
						.build(competition))
				.retrieve()
				.body(MatchesResponse.class);
		return response.matches().stream().map(this::toCompletedMatch).toList();
	}

	@Override
	public Optional<CompletedMatch> match(String sourceMatchId) {
		Match match = restClient.get()
				.uri("/matches/{id}", sourceMatchId)
				.retrieve()
				.body(Match.class);
		return Optional.ofNullable(match).map(this::toCompletedMatch);
	}

	private CompletedMatch toCompletedMatch(Match match) {
		return new CompletedMatch(
				1,
				UUID.randomUUID().toString(),
				new MatchRef(SOURCE, String.valueOf(match.id())),
				1,
				Instant.now(),
				match.utcDate(),
				toCompetition(match),
				toStage(match.stage()),
				Venue.HOME,
				new TeamRef(teamId(match.homeTeam())),
				new TeamRef(teamId(match.awayTeam())),
				toResult(match),
				List.of(),
				List.of(),
				List.of());
	}

	private Competition toCompetition(Match match) {
		return new Competition(String.valueOf(match.competition().id()), seasonYear(match), false);
	}

	private Result toResult(Match match) {
		String duration = match.score().duration();
		boolean shootout = "PENALTY_SHOOTOUT".equals(duration);
		boolean extraTime = !"REGULAR".equals(duration);
		return new Result(
				toResultKind(match.status()),
				goals(match.score().fullTime().home()),
				goals(match.score().fullTime().away()),
				extraTime,
				shootout);
	}

	private static int seasonYear(Match match) {
		String startDate = match.season().startDate();
		return startDate == null ? 0 : Integer.parseInt(startDate.substring(0, 4));
	}

	private static String teamId(FootballDataResponses.Team team) {
		return String.valueOf(team.id());
	}

	private static int goals(Integer value) {
		return value == null ? 0 : value;
	}

	private static ResultKind toResultKind(String status) {
		return switch (status) {
			case "AWARDED" -> ResultKind.AWARDED;
			case "SUSPENDED", "CANCELLED", "POSTPONED" -> ResultKind.ABANDONED;
			default -> ResultKind.PLAYED;
		};
	}

	/**
	 * football-data.org's stage names map loosely onto the formula's stages. This
	 * is a placeholder: the real cup-vs-continental distinction depends on the
	 * competition, which ADR-0017 open point 6 leaves to the mapping work.
	 */
	private static Stage toStage(String stage) {
		return switch (stage) {
			case "GROUP_STAGE" -> Stage.CONTINENTAL_GROUP;
			case "LAST_16", "QUARTER_FINALS", "SEMI_FINALS" -> Stage.CONTINENTAL_KNOCKOUT;
			case "FINAL" -> Stage.CONTINENTAL_FINAL;
			case "PRELIMINARY_ROUND", "FIRST_QUALIFYING_ROUND", "SECOND_QUALIFYING_ROUND",
					"THIRD_QUALIFYING_ROUND", "PLAY_OFF_ROUND" -> Stage.CONTINENTAL_QUALIFYING;
			default -> Stage.LEAGUE;
		};
	}
}
