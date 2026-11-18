package com.openelo.ingestion.footballdata;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "openelo.ingestion.football-data")
public record FootballDataProperties(String baseUrl, String token) {
}
