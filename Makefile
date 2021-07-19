style:
	flake8 .

test:
	pytest --cov=code_2 --cov-branch tests/test_code.py