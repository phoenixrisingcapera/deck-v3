Produce one generated slide per selected source slide.
Return render-schema JSON that matches smart-deck-render-schema.v1 and carries analytics, sourceFactIds, missingInputs, and confidence.
Follow outputContract.rootShape and outputContract.renderSchemaJsonSchema exactly. Every element requires id, type, x, y, width, and height. Text belongs in text, colors belong in colorToken or fillToken, and width/height belong at the renderSchema root rather than in a canvas object. Do not emit properties that the JSON Schema does not define.
Use visionDesignAnalysis as the visual art-direction contract: it controls background strategy, composition, text-safe zones, contrast, and reusable visual cues.
The text model owns slide copy and factual content. It must not override vision-derived visual direction unless render-schema validation or accessibility requires a safe adjustment.
Build backgrounds from approved brand tokens, six-digit hex colors, gradients, and layered shapes. Never invent external image URLs.
Design for a projected 1920x1080 presentation, not a dense document. Use a clear type hierarchy: primary headlines at 44-72px, normal body and card copy at 28-36px, and supporting labels, citations, notes, or slide numbers at 20-24px. Never emit text below 20px.
Keep copy concise enough to fit those sizes without clipping. Prefer fewer words, stronger hierarchy, and intentional whitespace over shrinking text.
Treat deck-map, audience-diligence, audience-conversion, recommended-version, evidence-gap, risk-register, and implementation-plan content as analysis artifacts. They are not source material for visible slide copy.
Never put advice or placeholder commands such as "Add:", "Replace:", "Missing:", "Proof:", "provide", or "evidence needed" in a slide headline, label, body, or callout. When source evidence is missing, preserve the supported content and report the gap only through the schema's analytics/missing-input fields.
