# Contributing Guide

## Development Setup

1. Fork the repository
2. Clone your fork
3. Create a virtual environment: python -m venv venv
4. Activate it: source venv/bin/activate
5. Install dev dependencies: pip install -r requirements-dev.txt
6. Run tests: pytest tests/ -v

## Code Style

- Format with Black: black src/ tests/
- Sort imports with isort: isort src/ tests/
- Lint with flake8: flake8 src/
- Type check with mypy: mypy src/

## Submitting Changes

1. Create a branch: git checkout -b feature/your-feature
2. Make changes and commit
3. Push to your fork
4. Submit a pull request
