package com.openelo.ingestion.footballdata;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

@Configuration
class FootballDataConfig {

	@Bean
	RestClient footballDataRestClient(FootballDataProperties properties) {
		return RestClient.builder()
				.baseUrl(properties.baseUrl())
				.defaultHeader("X-Auth-Token", properties.token())
				.build();
	}
}
