package com.openelo.market.common;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

// Development clock: stands still until set. The current instant is saved to a
// file on every change and read back at startup, so restarts (including devtools
// restarts) never move time.
public class ManualClock extends Clock {

	private static final Logger log = LoggerFactory.getLogger(ManualClock.class);

	private final Path file;

	private volatile Instant now;

	private ManualClock(Path file, Instant now) {
		this.file = file;
		this.now = now;
	}

	static ManualClock load(Path file) {
		ManualClock clock;
		if (Files.exists(file)) {
			clock = new ManualClock(file, read(file));
		} else {
			clock = new ManualClock(file, Instant.now());
			clock.save();
		}
		log.warn("Manual clock active at {} (saved in {})", clock.now, file.toAbsolutePath());
		return clock;
	}

	synchronized void set(Instant instant) {
		now = instant;
		save();
	}

	@Override
	public Instant instant() {
		return now;
	}

	@Override
	public ZoneId getZone() {
		return ZoneOffset.UTC;
	}

	// a view in another zone that still follows this clock
	@Override
	public Clock withZone(ZoneId zone) {
		ManualClock source = this;
		return new Clock() {
			@Override
			public Instant instant() {
				return source.instant();
			}

			@Override
			public ZoneId getZone() {
				return zone;
			}

			@Override
			public Clock withZone(ZoneId other) {
				return source.withZone(other);
			}
		};
	}

	// a corrupt file fails startup: silently falling back to real time could move time backwards
	private static Instant read(Path file) {
		try {
			return Instant.parse(Files.readString(file).trim());
		} catch (IOException e) {
			throw new UncheckedIOException("Cannot read manual clock file " + file, e);
		} catch (DateTimeParseException e) {
			throw new IllegalStateException("Manual clock file " + file + " does not hold an ISO instant", e);
		}
	}

	// write then rename, so a crash mid-write never leaves a half-written file
	private void save() {
		try {
			Path temp = file.resolveSibling(file.getFileName() + ".tmp");
			Files.writeString(temp, now.toString());
			Files.move(temp, file, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
		} catch (IOException e) {
			throw new UncheckedIOException("Cannot save manual clock file " + file, e);
		}
	}
}
