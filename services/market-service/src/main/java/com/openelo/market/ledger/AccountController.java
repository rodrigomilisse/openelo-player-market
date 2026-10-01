package com.openelo.market.ledger;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("accounts")
public class AccountController {

	record CreateAccountRequest(String owner) {
	}

	private final AccountRepository accounts;

	AccountController(AccountRepository accounts) {
		this.accounts = accounts;
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	Account create(@RequestBody CreateAccountRequest request) {
		return accounts.save(new Account(request.owner()));
	}

	@GetMapping
	List<Account> list() {
		return accounts.findAll();
	}
}
