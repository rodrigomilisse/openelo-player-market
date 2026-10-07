package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("users")
class SignUpController {

	private final SignUp signUp;

	SignUpController(SignUp signUp) {
		this.signUp = signUp;
	}

	record SignUpRequest(String owner) {
	}

	record SignUpResponse(UUID userId) {
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	SignUpResponse create(@RequestBody SignUpRequest request) {
		return new SignUpResponse(signUp.signUp(request.owner()).value());
	}
}
