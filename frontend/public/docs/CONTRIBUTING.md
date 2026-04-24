# Contributing to AccountSafe

This document defines the standards for contributing to AccountSafe. Read it completely before submitting code.

For API and configuration details, see the [`docs/`](docs/) directory.

---

## Table of Contents

- [Security Requirements](#security-requirements)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

---

## Security Requirements

AccountSafe is a security product. These rules are non-negotiable.

### The Iron Rules

1. **No secrets in version control.** API keys, passwords, tokens, and private keys must never be committed. Use environment variables exclusively.

2. **Client-side encryption only.** Sensitive data must be encrypted in the browser before transmission. The server must never receive plaintext credentials.

3. **No `any` type in TypeScript.** Use explicit types. `any` circumvents the type system and introduces risk.

4. **No `@ts-ignore` directives.** Fix the type error - do not silence it.

5. **No `console.log` in production code.** Use the structured logger in `frontend/src/utils/logger.ts`. Remove all debug statements before submitting.

6. **No `print()` statements in Python.** Use the `logging` module exclusively.

7. **No disabled security headers.** CORS, CSRF, and CSP configurations must not be weakened.

8. **Strict dependency versioning.** No `^` or `~` in `package.json`. Pin all versions exactly (e.g. `"react": "18.3.1"`). This prevents supply chain attacks via automatic upgrades.

9. **New dependencies require justification.** Review the package's security posture and transitive dependency count before adding it.

10. **Cryptographic code is off-limits without maintainer sign-off.** Do not modify encryption algorithms, key derivation parameters, or cryptographic primitives without explicit approval and a security review.

### Mandatory Security Review

The following changes require a security review before merge:

- Any change to `frontend/src/utils/encryption.ts`
- Any change to `backend/api/features/auth/zero_knowledge.py`
- Any change to `backend/api/features/security/` (sessions, canary traps, health score)
- Authentication or session management changes
- New API endpoints that handle sensitive data
- Changes to CORS, CSRF, or CSP policies
- Database schema changes involving encrypted fields
- Dependency updates to cryptography, JWT, or auth packages
- Changes to duress mode or canary trap logic

---

## Development Setup

### Prerequisites

| Tool | Min Version | Notes |
|------|-------------|-------|
| Python | 3.10 | **Windows:** use `py` launcher from python.org - not MSYS2 |
| Node.js | 18 | Includes npm |
| PostgreSQL | 15 | Must be running before starting the backend |
| Git | 2.40 | |

> **Windows Python:** Install from [python.org](https://www.python.org/downloads/) and tick "Add to PATH". Always use `py -m venv venv` (the Python Launcher), not `python -m venv venv`. The `python` command may resolve to MSYS2 or the Microsoft Store stub, both of which produce broken venvs on Windows.

### Fork and clone

```bash
# Fork on GitHub, then:
git clone https://github.com/YOUR-USERNAME/AccountSafe.git
cd AccountSafe
git remote add upstream https://github.com/pankaj-bind/AccountSafe.git
```

### Backend setup

```bash
cd backend
```

**Create and activate a virtual environment:**

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows - Command Prompt (recommended)
py -m venv venv
venv\Scripts\activate.bat

# Windows - PowerShell
py -m venv venv
.\venv\Scripts\Activate.ps1
# First-time only, if blocked by execution policy:
# Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Install dependencies:**

```bash
pip install -r requirements-local.txt
```

**Configure environment - create `backend/.env`:**

```env
DEBUG=True
SECRET_KEY=django-insecure-dev-only-key-change-in-production
DB_NAME=accountsafe
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

**Run migrations and start:**

```bash
python manage.py migrate
python manage.py runserver        # http://localhost:8000
```

### Frontend setup

```bash
cd frontend
npm install
npm start                         # http://localhost:3000
```

### Verify your setup

```bash
# Linux / macOS
make test-backend
make test-frontend

# Windows
scripts\run_tests.bat backend
scripts\run_tests.bat frontend

# Type checking
cd frontend && npx tsc --noEmit
```

---

## Project Structure

```
backend/
├── api/
│   ├── features/                  # All business logic lives here
│   │   ├── auth/                  # Authentication & Zero-Knowledge
│   │   │   ├── views.py           # Login, register, password reset
│   │   │   ├── zero_knowledge.py  # ZK auth, duress mode
│   │   │   ├── services.py        # Business logic
│   │   │   ├── serializers.py     # Request/response schemas
│   │   │   └── urls.py
│   │   ├── vault/                 # Vault management
│   │   │   ├── views.py           # Categories, organisations, profiles
│   │   │   ├── zk_views.py        # Zero-knowledge vault operations
│   │   │   └── services.py
│   │   ├── security/              # Security features
│   │   │   ├── views.py           # Health score, sessions, canary traps
│   │   │   └── services.py
│   │   └── shared_secret/         # Secure credential sharing
│   │       ├── views.py
│   │       └── services.py
│   ├── models.py                  # Database models (shared)
│   ├── tests/                     # pytest test suite
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_vault_api.py
│   │   └── test_zero_knowledge.py
│   └── utils/                     # Shared utilities
├── core/
│   ├── settings.py
│   └── urls.py
└── requirements-local.txt         # Pinned dev dependencies

frontend/src/
├── components/       # Shared UI components
├── contexts/         # React context providers (Auth, Panic, Theme, ...)
├── features/         # Feature-specific components
├── hooks/            # Custom React hooks
├── pages/            # Route-level components (one per page)
├── services/         # API client layer
├── types/            # TypeScript type definitions
└── utils/            # Shared utilities (encryption, logger, formatters, ...)
```

> **Do not add new views to `backend/api/views.py`.** All new features belong in `backend/api/features/{module}/`.

---

## Code Standards

### TypeScript (Frontend)

Strict mode is enabled in `tsconfig.json`. All of the following apply.

**Requirements:**
- Functional components only - no class components.
- Explicit return types on all functions.
- Interface definitions for all props and state shapes.
- Typed catch blocks: `catch (error: unknown)`.
- No `any`, no `@ts-ignore`.
- Imports ordered: React → external libraries → internal modules → types.
- Use the structured logger (`src/utils/logger.ts`), not `console.log`.

**Example:**

```typescript
interface ProfileCardProps {
  profile: Profile;
  onEdit: (id: number) => void;
  onDelete: (id: number) => void;
}

export const ProfileCard: React.FC<ProfileCardProps> = ({
  profile,
  onEdit,
  onDelete,
}): JSX.Element => {
  const handleEdit = (): void => {
    onEdit(profile.id);
  };

  return (
    <div className="rounded-lg border p-4">
      <h3>{profile.title}</h3>
      <button onClick={handleEdit}>Edit</button>
    </div>
  );
};
```

### Python (Backend)

PEP 8, formatted with Black (line length 88), linted with Flake8, imports sorted with isort.

**Requirements:**
- Type hints on all function signatures.
- Docstrings on all public functions and classes.
- Use `logging` module - never `print()`.
- Maximum line length: 88 characters.

**Example:**

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def encrypt_credential(plaintext: str, key: bytes) -> Optional[str]:
    """
    Encrypt a credential using AES-256-GCM.

    Args:
        plaintext: The string to encrypt.
        key: A 256-bit encryption key.

    Returns:
        Base64-encoded ciphertext, or None if encryption fails.

    Raises:
        ValueError: If plaintext is empty.
    """
    if not plaintext:
        raise ValueError("Plaintext cannot be empty")
    # ...
```

---

## Testing Requirements

### Coverage expectations

| Area | Minimum |
|------|---------|
| Encryption utilities | 90% |
| Authentication flows | 85% |
| API endpoints | 80% |
| UI components | 70% |

### Running the full test suite

**Linux / macOS:**
```bash
make test
```

**Windows:**
```bat
scripts\run_tests.bat
```

### Backend (pytest)

```bash
cd backend

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate.bat

python -m pytest -v
python -m pytest -v --cov=api --cov-report=term-missing   # with coverage
```

### Frontend (Jest)

```bash
cd frontend
npm test -- --watchAll=false                   # run once
npm test -- --watchAll=false --coverage        # with coverage report
```

### What to test

**Backend:**
- Unit tests for encryption/decryption logic
- Integration tests for API endpoints (use the Django test client, not mocks)
- Authentication flow tests - register, login, duress mode, session expiry
- Permission and access control tests

**Frontend:**
- Component rendering tests
- Custom hook behaviour tests
- Encryption utility tests (`src/utils/__tests__/`)
- Error boundary behaviour

---

## Commit Guidelines

Format: [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Use for |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `security` | Security fix or hardening |
| `refactor` | Code restructure with no behaviour change |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Build, dependency, or tooling changes |

### Rules

- Subject: imperative mood, no period, under 50 characters.
- Body: explain *what* and *why*, not *how*. Wrap at 72 characters.
- Reference issues in the footer: `Closes #123` or `Fixes #456`.

### Examples

```
feat(vault): add encrypted credential export

Implement JSON export of vault credentials using the existing
AES-256-GCM encryption key. Export is always encrypted - no
plaintext export path is provided.

Closes #234
```

```
security(auth): rate-limit login endpoint per IP

Add per-IP rate limiting to prevent brute-force attacks.
5 attempts per minute; 15-minute lockout on breach.

Refs #189
```

---

## Pull Request Process

### Checklist before submitting

- [ ] Code compiles without errors (`npx tsc --noEmit`)
- [ ] All tests pass (`make test` or `scripts\run_tests.bat`)
- [ ] No linting errors (`flake8 .` and `npm run lint`)
- [ ] Commits follow Conventional Commits format
- [ ] No secrets, `.env` files, or credentials in the diff
- [ ] Documentation updated if behaviour changed
- [ ] Security-sensitive changes flagged for review

### Submission

1. Push your branch to your fork.
2. Open a pull request against `main`.
3. Fill out the PR template completely - incomplete PRs will not be reviewed.
4. Request review from a maintainer.

### PR title format

Same convention as commit messages:

```
feat(vault): add credential search
fix(auth): resolve session timeout race condition
security(api): patch IDOR vulnerability in profile endpoint
```

### Review process

1. All CI checks must pass.
2. At least one maintainer approval required.
3. Security-sensitive changes require two approvals.
4. Address every review comment before merge.
5. Commits are squashed on merge.

---

## Issue Reporting

### Bugs

Include:
1. **Title** - specific and descriptive.
2. **Environment** - OS, browser, Python/Node versions.
3. **Steps to reproduce** - minimal numbered steps.
4. **Expected behaviour** - what should happen.
5. **Actual behaviour** - what happens instead.
6. **Logs / screenshots** - sanitise any sensitive data before pasting.

### Feature requests

Include:
1. **Problem statement** - what problem does this solve?
2. **Proposed solution** - how should it work?
3. **Alternatives considered** - other approaches you evaluated.
4. **Security implications** - any security considerations.

### Security vulnerabilities

Do not open public issues for security vulnerabilities.

Follow the responsible disclosure process in [SECURITY.md](SECURITY.md).

---

## Questions

1. Search existing issues and discussions first.
2. Open a GitHub Discussion for general questions.
3. Contact maintainers directly for security-related questions.
