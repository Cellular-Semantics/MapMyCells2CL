# Development Guide

You are an experienced Python developer whos build production quality libraries.

## Development philosophy

### Exploratory phase

Initial exploratory phase develops technical implementation from initial mix fo functional & technical specs.  
This phase does not follow TDD or code quality checks, it consists solely of building exporatory scripts.
The end of the exploratory phase results in a ROADMAP with tech specs for an  MCP

### MVP phase

Develop MVP to beta release on PyPi for community testing.

### Refinenent phase

Refine & fix bugs in reesponds to testing.


## Code quality:

Use MyPy for type testing.  Run these tests before Ruff

Use Ruff for linting and code layout.

```bash
# Install pre-commit hooks
uv run pre-commit install

# These now run automatically on commit
uv run pytest --cov --cov-fail-under=80
uv run mypy src/
uv run ruff check src/ tests/
uv run ruff format src/ tests/

```

- ✅ `experiments/` is the home for exploratory scripts — write freely, no TDD required

Also run as CI/CD GitHub Actions on all PRs

## Test-Driven Development

Aim 80% coverage

### Integration Tests: ALWAYS Required

**From Day 1:**
- Integration tests with REAL external services (MOCKS ARE ONLY ACCEPTABLE FOR RUNNING ON GITHUB)
- Tests FAIL HARD if no API keys
- Forces validation against real behavior
- Catches API quirks immediately

**Example:**
```python
@pytest.mark.integration
def test_perplexity_json_output():
    """Test real Perplexity API with JSON schema."""
    if not os.getenv("PERPLEXITY_API_KEY"):
        pytest.fail("PERPLEXITY_API_KEY required for integration tests")

    # Test with real API
    result = query_perplexity(...)
    assert valid_json(result)
```

### TDD: When to Use

**Use TDD for:**
- ✅ Parsers, validators, data transformers (clear inputs/outputs)
- ✅ Bug fixes (red → green → refactor)
- ✅ Core domain logic (once understood)

**Don't use TDD for:**
- ❌ Exploratory prototypes
- ❌ Initial API integration experiments

**TDD Workflow:**
```bash
# 1. Red: Write failing test
uv run pytest tests/test_parser.py -k test_new_feature  # Should fail

# 2. Green: Minimal implementation
# ... write code ...
uv run pytest tests/test_parser.py -k test_new_feature  # Should pass

# 3. Refactor: Improve while tests stay green
```

---

## Testing Commands (using uv)

```bash
# Environment setup
uv sync --dev            # Install all dependencies including dev tools

# Running tests
uv run pytest                    # All tests
uv run pytest -m unit           # Unit tests only (CI uses this)
uv run pytest -m integration    # Integration tests (local only)
uv run pytest --cov             # With coverage
uv run pytest --cov --cov-fail-under=60   # MVP phase
uv run pytest --cov --cov-fail-under=80   # Post-MVP phase

# Code quality
uv run mypy src/                      # Type check
uv run ruff check --fix src/ tests/   # Lint + auto-fix
uv run ruff format src/ tests/        # Format

# Documentation
python scripts/check-docs.py          # Build and check docs
cd docs && uv run sphinx-build . _build/html -W  # Alternative

# Pre-commit (Post-MVP)
uv run pre-commit install             # Install hooks
uv run pre-commit run --all-files     # Run on all files

# Dependencies
uv add requests              # Runtime dependency
uv add --dev pytest          # Dev dependency
```

---

## Required Test Structure

```
tests/
├── unit/                    # Fast, isolated, no external deps
│   ├── test_parsers.py
│   ├── test_validators.py
│   └── ...
├── integration/             # Real external services
│   ├── test_perplexity.py
│   ├── test_deepsearch.py
│   └── ...
└── conftest.py             # Shared fixtures
```

**All tests must use markers:**
```python
@pytest.mark.unit          # Unit test
@pytest.mark.integration   # Integration test
```

**Integration test requirements:**
- Real API connections (no mocks)
- Fail hard if no credentials
- Document expected behavior
- Test error modes (rate limits, network failures)

---

## Integration Testing Strategy

### Local Development (Real APIs)
- Integration tests REQUIRE real API keys
- Tests FAIL HARD if credentials missing
- Forces validation against real services
- Run: `uv run pytest -m integration`

### CI/GitHub Actions (Unit Tests Only)
- NO integration tests in CI (avoid API costs/mocking)
- Only unit tests (fast, reliable)
- Run: `uv run pytest -m unit`

**Rationale:**
- Local: Mandatory real API testing ensures quality
- CI: Simple, fast validation
- Avoids mock complexity and false confidence

---

## FORBIDDEN Patterns

**Never:**
- ❌ Mock data for integration tests (use real APIs)
- ❌ Simulated API responses in integration tests
- ❌ Skipping tests with `pytest.mark.skip` (fix or remove)
- ❌ Ring 1+ features before Ring 0 ships
- ❌ Building generic architecture before specific case works
- ❌ Rewriting existing code without documented reason

**Required:**
- ✅ Real API integration tests from Day 1
- ✅ Ship Ring 0 within 2-3 weeks
- ✅ Get user feedback before Ring 1
- ✅ Extend existing code when possible

---

## Documentation Requirements

**Google-style docstrings:**
```python
def query_deepsearch(gene_list: list[str], model: str = "sonar-pro") -> dict:
    """Query DeepSearch API for gene program annotation.

    Args:
        gene_list: List of gene symbols to annotate
        model: DeepSearch model to use (default: sonar-pro)

    Returns:
        Dictionary containing annotation results with keys:
        - programs: List of identified gene programs
        - citations: Supporting references
        - confidence: Confidence scores

    Raises:
        APIError: If DeepSearch request fails
        ValidationError: If response doesn't match schema

    Example:
        .. code-block:: python

            result = query_deepsearch(["TP53", "BRCA1"])
            programs = result["programs"]
    """
```

**RST syntax in docstrings:**
- Use `.. code-block:: python` (not markdown backticks)
- Check with: `python scripts/check-docs.py`

**Documentation structure:**
- Auto-generated API docs (Sphinx + AutoAPI)
- Manual guides in docs/ (MyST markdown)
- ALWAYS run docs check before committing

---

## Planning Requirements

### For Each Feature

**Include:**
1. Clear, testable goal
2. Integration test demonstrating real API behavior
3. Error handling for actual failure modes:
   - Network failures
   - Malformed data
   - Rate limits
   - Authentication errors
4. Critique: Potential issues/risks with approach

**Template:**
```markdown
## Feature: [Name]

### Goal
[What value does this provide?]

### Integration Test
[How will we test with real APIs?]

### Error Modes
- Network failure: [handling]
- Malformed response: [handling]
- Rate limit: [handling]

### Critique
- Risk 1: [mitigation]
- Risk 2: [mitigation]
```

### MVP Definition

**Each feature is not complete until:**
- ✅ Real integration test passes
- ✅ Error handling implemented
- ✅ Documented in code and docs

**This CLAUDE.md guides the agent. Keep it updated as decisions evolve.**
