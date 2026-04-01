.PHONY: install test lint run clean

install:
	pip install -r requirements.txt

test:
	python -m pytest tests/ -v

lint:
	python -m flake8 src/ --max-line-length=120
	python -m black src/ --check

format:
	python -m black src/
	python -m isort src/

run:
	python main.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

setup-db:
	python scripts/setup_database.py

seed:
	python scripts/seed_data.py

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f bot
