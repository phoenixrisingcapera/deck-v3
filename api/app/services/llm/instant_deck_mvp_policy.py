"""Application-owned scope for new Instant Deck MVP requests."""

MVP_POLICY_VERSION = "instant-deck-investor-mvp.v1"
MVP_AUDIENCE = "VC / Investors"
MVP_PURPOSE = "Redesign the uploaded company deck for investor evaluation."
MVP_UPLOAD_PROMPT = (
    MVP_PURPOSE + " Build a coherent investor narrative from the supplied evidence, "
    "preserving source facts, useful assets and brand identity. Choose slide count from the content. "
    "Record missing evidence honestly; never invent traction, revenue, team credentials, market figures "
    "or a funding request."
)
