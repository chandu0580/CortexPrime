# Contributing to CortexPrime

## Getting Started

1. Fork the repository.
2. Clone your fork: `git clone https://github.com/your-username/cortexprime.git`
3. Set up the development environment:
   - Copy `.env.example` to `.env` and fill in required values
   - Run `docker compose up -d` to start infrastructure (Postgres, Redis, RabbitMQ, Neo4j, MinIO)
   - Backend: `pip install -r requirements.txt -r requirements-dev.txt`
   - Frontend: `cd frontend && npm ci --legacy-peer-deps`

## Code Standards

### Backend (Python)
- **Python version:** 3.11
- **Formatter/Linter:** Ruff (`ruff check backend/`)
- **Type checking:** mypy (`mypy backend/`)
- **Line length:** 120 characters
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes
- All new code must include type annotations.

### Frontend (TypeScript/React)
- **Node version:** 20.x
- **Package manager:** npm
- **Linter:** ESLint (`npm run lint` in `frontend/`)
- **Type checking:** `npx tsc --noEmit`
- **Framework:** Next.js 16 (App Router)
- **Styling:** TailwindCSS v4 (CSS variables for theming)
- **State management:** Zustand stores
- **API calls:** TanStack React Query
- **Animation:** Framer Motion (use motion tokens from `@/lib/motion-tokens`)
- **Naming:** `camelCase` for variables/functions, `PascalCase` for components

## Testing

### Backend tests
```bash
pytest tests/ -v --cov=backend --cov-report=term-missing
```
- Tests go in `tests/` directory
- Use pytest-asyncio for async tests
- Coverage threshold: 45%

### Frontend tests
```bash
cd frontend && npm test
```
- Tests go in `frontend/tests/` directory
- Use Vitest + Testing Library
- Component tests should use `@testing-library/react`

### Load testing
```bash
cd tests/load && k6 run k6-smoke.js
```

## Pull Request Process

1. Create a feature branch from `develop`
2. Write tests for new functionality
3. Ensure all tests pass and coverage meets threshold
4. Run linting: `ruff check backend/` + `npm run lint`
5. Run type checking: `mypy backend/` + `npx tsc --noEmit`
6. Update documentation if needed
7. Open a PR against `develop` with a clear description

## Commit Messages

Follow conventional commits:
- `feat:` — new feature
- `fix:` — bug fix
- `refactor:` — code restructuring
- `test:` — adding/updating tests
- `docs:` — documentation changes
- `chore:` — tooling, CI, dependencies

## Branch Strategy

- `main` — production releases
- `develop` — integration branch
- `feature/*` — feature branches
- `release/*` — release candidates
- `fix/*` — bug fixes

## Need Help?

- Check `docs/` for comprehensive documentation
- Review `docs/TROUBLESHOOTING_GUIDE.md` for common issues
- Open a GitHub Discussion for questions

## Security

Report security vulnerabilities to ops@cortexprime.ai — do not open public issues.
