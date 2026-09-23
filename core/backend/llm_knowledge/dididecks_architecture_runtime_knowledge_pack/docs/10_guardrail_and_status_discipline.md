# Guardrails and Status Discipline

A page existing is not enough.

A feature is only ready when:

- the route exists
- the component exists
- the data model is aligned
- build passes
- typecheck passes
- API boundary is correct
- frontend/backend boundary is respected
- architecture drift is documented or fixed

## Severity model

- critical
- blocker
- warning
- architecture_drift
- info

## Examples of architecture drift

- editor uses local-only slide objects
- no persistent field binding in blocks
- docs claim route shipped while route missing
- DidiDecks uses `/api/v1`
- CI only builds splash/marketing route
- no version/audit concept for accepted AI changes
