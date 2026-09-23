# Frontend Boundary

The frontend may contain:

- routes
- mock data
- view models
- typed API clients
- UI shells
- local interaction state
- placeholder actions
- public env variables
- documentation

The frontend must not contain:

- database credentials
- Stripe secret keys
- OpenAI API keys
- backend persistence logic
- model training pipelines
- private prompt pipelines
- export workers
- server-side guardrail policy engines

## Local editor state is not truth

The editor may track:

```ts
activeSlideId
activeVariantKey
selectedBlockId
zoom
dirty
```

But product truth lives in the backend:

```txt
decks
slides
blocks
persistent fields
field usages
versions
audit logs
rebuild jobs
```
