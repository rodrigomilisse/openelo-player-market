package com.openelo.market.projection;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("curve/shares")
class SupplyController {

	// TODO when ADR-0015 is applied: minus the active pool's balance, found through
	// pool:{shareId} (ADR-0015 decision 16)
	@GetMapping("{shareId}/supply")
	@ResponseStatus(HttpStatus.NOT_IMPLEMENTED)
	void supply(@PathVariable UUID shareId) {
	}
}
