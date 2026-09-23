# GitHub and Deployment Readiness

Before pushing or deploying, verify:

- no `.env` or `.env.local`
- no real secrets
- no `node_modules`
- no `.next` build outputs
- no old legacy repo code
- no backend logic in frontend
- build passes
- typecheck passes
- lint result documented
- API prefix uses `/api/products/dididecks`

## Repository status labels

- READY_FOR_GITHUB: clean scaffold, safe to push, product gaps documented
- PARTIAL: safe work exists but blockers/warnings remain
- NOT_READY: build/typecheck fails, secrets found, or boundary violation exists
