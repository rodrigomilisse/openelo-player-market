package com.openelo.market.user;

import com.openelo.market.ledger.account.AccountService;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("users")
public class UserController {

	private UserRepository userRepository;

	private AccountService accountService;

	record CreateUserRequest(String owner) {
	}

	public UserController(UserRepository userRepository, AccountService accountService) {
		this.userRepository = userRepository;
		this.accountService = accountService;
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	IUser create(@RequestBody CreateUserRequest request) {
		User user = new User(request.owner());
		userRepository.save(user);
		accountService.createAccount(user);
		return user;
	}

	@GetMapping
	List<User> list() {
		return userRepository.findAll();
	}
}
