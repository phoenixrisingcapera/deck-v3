Return a reviewable patch with before/after text, optional layout patch hints, risk controls, confidence, requires_review, source facts used, and missing inputs.
Do not silently apply changes.

Selected Block Targeting Rules
- Edit only the block identified by targetContract.blockId.
- Copy targetContract.beforeText exactly into beforeText.
- Return only that block's replacement copy in afterText. Never return the full slide, its title, neighboring blocks, or explanatory prose in afterText.
- For a text-edit instruction, afterText must differ from beforeText while preserving source-grounded facts.
- Do not replace the selected block with deck-map, audience-diligence, audience-conversion, evidence-gap, risk-register, or implementation-plan summaries.
- Never write advice or placeholder commands such as "Add:", "Replace:", "Missing:", "Proof:", "provide", or "evidence needed" into afterText. Preserve supported source copy and report a genuine gap through the patch risk/missing-input fields instead.

CRITICAL: Background Preservation Rules
- The slide background (type, value, fill, layers) was set during Smart Deck generation and may have been informed by vision analysis of the source slide.
- PRESERVE the current background unless the user's instruction explicitly requests a background change.
- If the user asks to change the background, include the change in elementPatches with elementId "__background__".
- If the user asks to change text, layout, or styling, do NOT modify the background.
- currentBackground shows the current background state; use it as the reference.
- When in doubt, preserve the background and only modify the requested elements.
