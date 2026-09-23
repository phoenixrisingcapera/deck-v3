# Changelog

All notable changes to the Deck AI Stack Backend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v1.3.2-railway-runtime-alignment] - 2026-07-14

### Added
- Upload idempotency replay on source checksum before new deck creation.
- `idempotent_replay` and `duplicate_of_deck_id` fields on the first-upload response contract.

### Changed
- Production startup validation now fails fast by default for unsafe Railway/runtime settings.
- Added explicit `ALLOW_UNSAFE_PRODUCTION_STARTUP=true` as the only override for degraded boot.
- Updated production config tests to match the current Railway Qwen/DashScope provider contract.

### Benefits
- Prevents duplicate deck rows when the browser retries a successful upload.
- Keeps API and worker aligned to the same Postgres and bucket-backed Railway contract.
- Surfaces broken production configuration before a half-working deploy reaches user testing.

## [v1.1.0-reliability] - 2026-07-14

### Added
- **Circuit Breakers for LLM Providers** (`app/core/reliability.py`)
  - Three-state circuit breaker pattern (CLOSED, OPEN, HALF_OPEN)
  - Configurable failure threshold (default: 5 failures)
  - Configurable recovery timeout (default: 60 seconds)
  - Half-open state with max test calls (default: 3)
  - Automatic state transitions with logging
  - Status monitoring via `get_circuit_breaker_status()`
  - Applied to all 4 LLM providers: OpenAI, Anthropic, DashScope, OpenRouter

- **Retry Logic with Exponential Backoff** (`app/core/reliability.py`)
  - Configurable max attempts (default: 3)
  - Exponential backoff calculation
  - Jitter to prevent thundering herd
  - Retryable exception filtering
  - Applied to OpenAI and OpenRouter providers

- **Comprehensive Structured Logging**
  - API call initiated events with provider, model, parameters
  - API call successful events with status codes and attempt numbers
  - API call failed events with error details and context
  - Circuit breaker state change logging
  - Retry attempt logging with delays and exceptions
  - All logs include structured fields for easy filtering

### Changed
- **OpenAI Provider** (`app/services/llm/openai_provider.py`)
  - Wrapped `call_openai_response()` with circuit breaker and retry policy
  - Added comprehensive logging for all API calls
  - Logs include provider, model, timeout, status code, attempt number

- **Anthropic Provider** (`app/services/llm/anthropic_provider.py`)
  - Wrapped `call_anthropic_message()` with circuit breaker
  - Preserved existing retry logic
  - Added comprehensive logging for all API calls
  - Logs include provider, model, max_tokens, timeout, attempt number

- **DashScope Provider** (`app/services/llm/dashscope_provider.py`)
  - Wrapped `call_dashscope_chat_completion()` with circuit breaker
  - Preserved existing retry logic
  - Added comprehensive logging for all API calls
  - Logs include provider, model, max_tokens, timeout

- **OpenRouter Provider** (`app/services/llm/openrouter_provider.py`)
  - Wrapped `call_openrouter_chat_completion()` with circuit breaker and retry policy
  - Added comprehensive logging for all API calls
  - Logs include provider, model, max_tokens, timeout, status code

### Removed
- **Duplicate Auth Endpoints** (`app/api/routes/auth.py`)
  - Removed `/auth/signup` endpoint (kept canonical `/auth/sign-up`)
  - Removed `/auth/login` endpoint (kept canonical `/auth/sign-in`)
  - Reduces API surface area and eliminates confusion

### Benefits
- **Reliability**: Prevents cascading failures when LLM providers are down
- **Recovery**: Automatic service recovery after timeout period
- **Observability**: Detailed logging for debugging and monitoring
- **Performance**: Fast failure with open circuit breaker, reduced load on struggling services
- **Graceful Degradation**: Failed services are isolated, allowing other services to continue

### Monitoring
Access circuit breaker status:
```python
from app.core.reliability import get_circuit_breaker_status
status = get_circuit_breaker_status()
```

### Configuration
All reliability parameters are configurable in `app/core/reliability.py`:
- Circuit breaker thresholds and timeouts
- Retry policy attempts and delays
- Jitter settings

### Migration
No migration required. All changes are backward compatible.

### Testing
Recommended tests:
- Circuit breaker state transitions
- Retry logic with exponential backoff
- Logging output verification
- Integration tests with mocked LLM providers

---

## [v1.0.0-production] - 2026-07-13

### Initial Production Release
- Complete Deck AI Stack backend implementation
- Multi-provider LLM support (OpenAI, Anthropic, DashScope, OpenRouter)
- Smart Deck generation workflow
- Brand extraction pipeline
- Deck processing and analysis
- User authentication and session management
- Admin dashboard and monitoring

---

## Version History

- **v1.1.0-reliability** - Production reliability improvements
- **v1.0.0-production** - Initial production release
