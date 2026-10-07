package com.openelo.market.user;

import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// creating users happens in trading's SignUpController, which also opens their wallet
@RestController
@RequestMapping("users")
public class UserController {

	private UserRepository userRepository;

	public UserController(UserRepository userRepository) {
		this.userRepository = userRepository;
	}

	@GetMapping
	List<User> list() {
		return userRepository.findAll();
	}
}
