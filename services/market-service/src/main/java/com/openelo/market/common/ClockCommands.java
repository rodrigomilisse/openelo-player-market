package com.openelo.market.common;

import java.time.DateTimeException;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class ClockCommands {

	private static final Pattern DURATION = Pattern.compile("(-?)(\\d+)(min|h|d|mo|y)");

	private static final Pattern DATE = Pattern.compile("(\\d{1,2})([a-z]{3})(\\d{2}|\\d{4})");

	private static final Pattern TIME = Pattern.compile("(\\d{1,2}):(\\d{2})");

	private static final List<String> MONTHS = List.of("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
			"oct", "nov", "dec");

	private ClockCommands() {
	}

	static Instant apply(String command, Instant now) {
		if (command == null || command.isBlank()) {
			throw new IllegalArgumentException(usage("Empty command."));
		}
		ZonedDateTime time = now.atZone(ZoneOffset.UTC);
		for (String token : command.trim().toLowerCase(Locale.ROOT).split("\\s+")) {
			time = applyToken(token, time);
		}
		return time.toInstant();
	}

	private static ZonedDateTime applyToken(String token, ZonedDateTime time) {
		try {
			Matcher m = DURATION.matcher(token);
			if (m.matches()) {
				long amount = Long.parseLong(m.group(2));
				if (!m.group(1).isEmpty()) {
					amount = -amount;
				}
				return switch (m.group(3)) {
					case "min" -> time.plusMinutes(amount);
					case "h" -> time.plusHours(amount);
					case "d" -> time.plusDays(amount);
					case "mo" -> time.plusMonths(amount); // 31jan + 1mo = 28/29feb
					default -> time.plusYears(amount);
				};
			}
			m = DATE.matcher(token);
			if (m.matches()) {
				int month = MONTHS.indexOf(m.group(2)) + 1;
				if (month == 0) {
					throw new IllegalArgumentException(usage("Unknown month '" + m.group(2) + "'."));
				}
				LocalDate date = LocalDate.of(year(m.group(3)), month, Integer.parseInt(m.group(1)));
				return time.with(date);
			}
			m = TIME.matcher(token);
			if (m.matches()) {
				return time.with(LocalTime.of(Integer.parseInt(m.group(1)), Integer.parseInt(m.group(2))));
			}
		} catch (DateTimeException | ArithmeticException e) {
			throw new IllegalArgumentException(usage("'" + token + "' is not a valid date or time: " + e.getMessage() + "."));
		}
		throw new IllegalArgumentException(usage("Unknown command '" + token + "'."));
	}

	// two digits: 50-99 → 1950-1999, 00-49 → 2000-2049
	private static int year(String digits) {
		int year = Integer.parseInt(digits);
		if (digits.length() == 4) {
			return year;
		}
		return year >= 50 ? 1900 + year : 2000 + year;
	}

	private static String usage(String problem) {
		return problem + " Use e.g. 1y, 3mo, 2d, 4h, 30min, -1d, 05mar26, 05mar2026, 14:30.";
	}
}
