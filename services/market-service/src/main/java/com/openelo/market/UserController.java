package com.openelo.market;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
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

	@Autowired
	private UserRepository users;

	@Autowired
	private AccountService accountService;

	record CreateUserRequest(String owner) {
	}

	public UserController(UserRepository users, AccountService accountService) {
		this.users = users;
		this.accountService = accountService;
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	IUser create(@RequestBody CreateUserRequest request) {
		User user = new User(request.owner());
		users.save(user);
		accountService.createAccount(user);
		return user;
	}

	@GetMapping
	List<User> list() {
		return users.findAll();
	}
}
