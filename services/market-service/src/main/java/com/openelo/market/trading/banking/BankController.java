package com.openelo.market.trading.banking;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.openelo.market.common.Id;
import com.openelo.market.user.IUser;

@RestController
@RequestMapping("bank")
public class BankController {

	BankService bankService;

	BankController(BankService bankService) {
		this.bankService = bankService;
	}

	record BankRequest(Id<IUser> userId, long amount) {
	}

	@PostMapping("deposit")
	@ResponseStatus(HttpStatus.CREATED)
	public void deposit(@RequestBody BankRequest request) {
		bankService.deposit(request.userId, request.amount);
	}

	@PostMapping("withdraw")
	@ResponseStatus(HttpStatus.CREATED)
	public void withdraw(@RequestBody BankRequest request) {
		bankService.withdraw(request.userId, request.amount);
	}
}
