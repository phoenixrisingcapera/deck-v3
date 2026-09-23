"""Inert, quarantined evidence handoff. This type is never a render artifact.

The ordinary compiler remains the only producer of publishable documents. This
preparation resolves provable metadata omissions and exposes every remaining
claim to factual review without treating an absent reference as fabrication.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re
import xml.etree.ElementTree as ET

from app.services.rendering import html_deck_compiler as compiler

HANDOFF_POLICY = 'inert-source-reference-handoff.v1'


@dataclass(frozen=True)
class QuarantinedCandidate:
    # Internal sanitized tree serialization, never sent to a browser or model.
    internal_html: str
    claims: tuple[dict, ...]
    diagnostics: tuple[dict, ...]
    slide_count: int
    compilation_hash: str  # Application-owned candidate binding, not proof.


def _identity(text):
    return compiler._normalized_heading_identity(text)


def _exact_fact(text, facts):
    # A bare magnitude has no metric meaning. Leave it for contextual review.
    if not re.search(r'[^\d\s.,%€$£+−–—-]', text):
        return None
    matches = [f for f in facts if _identity(f['text']) == _identity(text)]
    if not matches:
        return None
    # Equivalent duplicate source records are acceptable only on the same page.
    if len({tuple(f.get('sourceSlideIds', [])) for f in matches}) != 1:
        return None
    return min(matches, key=lambda f: (f.get('field') != 'title', f['factId']))


def _cover_title(text, facts):
    """Exact leading source lines + one canonical title, never a guessed name."""
    words = text.split()
    if not 1 <= len(words) <= 6 or re.search(r'\d', text):
        return None
    titles = [f for f in facts if f.get('field') == 'title'
              and _identity(f['text']).startswith(_identity(text) + ' ')]
    if len(titles) != 1:
        return None
    title = titles[0]
    for fact in facts:
        if fact.get('sourceSlideIds') != title.get('sourceSlideIds') or not str(fact.get('field','')).startswith('block:'):
            continue
        lines = [line.strip() for line in fact['text'].splitlines() if line.strip()]
        for end in range(1, min(6, len(lines))):
            if _identity(' '.join(lines[:end])) == _identity(text):
                return title
    return None


def _correct_lineage_from_bound_evidence(slide, *, source_ids, facts, ordinal):
    """Repair only lineage that is already proven by canonical evidence bindings.

    Provider-authored source identifiers are not authoritative.  When a section
    includes an unknown identifier, the application may remove it and rebuild
    the ordered lineage from (a) canonical identifiers already declared on the
    section and (b) canonical sourceSlideIds owned by its exact data-source-refs.
    No textual content, fact binding, visual metadata, style, or geometry is
    changed, and an unbound unknown identifier still fails closed.
    """
    declared = compiler._lineage_ids(slide, allow_missing=True)
    canonical = set(source_ids)
    invalid = sorted(set(declared) - canonical)
    evidence_refs: list[str] = []
    evidence_sources: set[str] = set()
    for node in slide.iter():
        for ref in (node.get('data-source-refs') or '').split():
            if ref in evidence_refs:
                continue
            fact = facts.get(ref)
            if fact is None:
                continue
            evidence_refs.append(ref)
            evidence_sources.update(
                source_id for source_id in fact.get('sourceSlideIds', [])
                if source_id in canonical
            )
    retained = {source_id for source_id in declared if source_id in canonical}
    corrected = [source_id for source_id in source_ids if source_id in retained | evidence_sources]
    needs_correction = bool(invalid) or (not declared and bool(corrected))
    if not needs_correction:
        return declared, None
    if invalid and not corrected:
        raise compiler.HtmlDeckCompileError(
            'source_lineage_unknown',
            'Unknown source lineage.',
            issues=[{
                'severity': 'error', 'category': 'provenance',
                'code': 'source_lineage_unknown',
                'message': 'A generated section referenced source IDs outside the canonical registry.',
                'blocking': True, 'repairable': True,
                'generationStage': 'pre_factual_review_lineage_validation',
                'sectionOrdinal': ordinal,
                'invalidSourceSlideIds': invalid,
                'declaredSourceSlideIds': declared,
                'expectedSourceSlideIds': source_ids,
            }],
        )
    slide.set('data-source-slide-ids', ' '.join(corrected))
    slide.attrib.pop('data-source-slide-refs', None)
    return corrected, {
        'code': 'source_lineage_corrected',
        'sectionOrdinal': ordinal,
        'previousSourceSlideIds': declared,
        'correctedSourceSlideIds': corrected,
        'invalidSourceSlideIds': invalid,
        'supportingSourceFactIds': evidence_refs,
        'generationStage': 'pre_factual_review_lineage_correction',
        'publicationBlocking': False,
    }


def prepare_candidate(raw, *, context, compiler_version, max_html_bytes=None):
    ceiling = compiler.whole_deck_html_ceiling(compiler_version=compiler_version, bound_max_html_bytes=max_html_bytes)
    if not raw.strip() or len(raw.encode()) > ceiling:
        raise compiler.HtmlDeckCompileError('html_budget_exceeded', 'Deck HTML exceeds its byte budget.')
    root = compiler._parse_document(compiler._strip_provider_fence(raw))
    # Reject active markup before even constructing the inert reviewer input.
    for node in root.iter():
        if compiler._local_name(node.tag) in compiler._DROP_WITH_CONTENT or any(
            compiler._local_name(a).lower().startswith('on') or compiler._local_name(a).lower() in {'srcdoc','formaction'}
            for a in node.attrib
        ):
            raise compiler.HtmlDeckCompileError('active_content_forbidden', 'Active content cannot enter factual review.')
    assets = context.get('approvedAssets') or []
    references = {a['assetId']:a['resolvedDataUrl'] for a in assets if a.get('resolvedDataUrl')}
    alt = {a['assetId']:a.get('altText') or a.get('label') or '' for a in assets}
    css, _ = compiler._sanitize_tree(root, references, alt, compiler_version=compiler_version)
    # Run the unchanged CSS gate now and again in final compilation. Keep CSS
    # internal: the reviewer receives claims only, with no executable markup.
    compiler.sanitize_and_scope_css('\n'.join(css), compiler_version=compiler_version)
    head = next(n for n in root.iter() if compiler._local_name(n.tag) == 'head')
    style = ET.SubElement(head, compiler._HTML_NS + 'style')
    style.text = '\n'.join(css)
    slides = compiler._extract_slides(compiler._find_deck_root(root))
    if len(slides) > compiler.MAX_SLIDES:
        raise compiler.HtmlDeckCompileError('slide_budget_exceeded', 'Deck exceeds its slide budget.')
    source_ids = [s['sourceSlideId'] for s in context['sourceSlides']]
    facts = {f['factId']:f for f in context['sourceFacts']}
    pages = {source:i for i,source in enumerate(source_ids, 1)}
    claims, diagnostics = [], []
    for ordinal, slide in enumerate(slides, 1):
        lineage, lineage_diagnostic = _correct_lineage_from_bound_evidence(
            slide, source_ids=source_ids, facts=facts, ordinal=ordinal,
        )
        if lineage_diagnostic is not None:
            diagnostics.append(lineage_diagnostic)
        local_facts = [f for f in facts.values() if f.get('sourceSlideIds') and set(f['sourceSlideIds']) <= set(lineage)]
        slide.set('data-da-slide-root', f'quarantine-{ordinal}')
        parents = {child:parent for parent in slide.iter() for child in parent}
        owners = set()
        for node in list(slide.iter()):
            tag = compiler._local_name(node.tag)
            text = compiler._independent_claim_text(node)
            original_refs = (node.get('data-source-refs') or '').split()
            parent = parents.get(node)
            owned = False
            while parent is not None:
                if parent in owners and not original_refs and tag not in compiler._FACTUAL_TEXT_TAGS:
                    owned = True
                    break
                parent = parents.get(parent)
            if owned:
                continue
            if not text or tag not in (compiler._FACTUAL_TEXT_TAGS | compiler._GROUNDED_INLINE_TAGS | {'small','text','tspan','figcaption','caption','blockquote','dt','dd','div'}):
                continue
            if tag == 'div' and len(node):
                continue
            owners.add(node)
            presentation = compiler._unbound_text_is_clearly_presentational(text)
            refs = original_refs[:]
            mapping = None
            if not presentation and (not refs or any(ref not in facts for ref in refs)):
                match = _exact_fact(text, local_facts)
                if match is None and ordinal == 1 and tag == 'h1' and lineage == source_ids[:1]:
                    match = _cover_title(text, local_facts)
                    mapping = 'verified_cover_title' if match else None
                elif match:
                    mapping = 'exact_source_text'
                if match:
                    refs = [match['factId']]
                    node.set('data-source-refs', ' '.join(refs))
            # small is a valid typographic wrapper, not a grounding target.
            # Preserve its typography and move only a proved leaf binding onto
            # the already-supported span. No new attribute/tag allowance.
            if tag == 'small' and refs and not len(node) and all(ref in facts for ref in refs):
                child = ET.SubElement(node, compiler._HTML_NS + 'span')
                child.text = node.text
                node.text = None
                child.set('data-source-refs', node.attrib.pop('data-source-refs'))
                node = child
                mapping = (mapping + '+' if mapping else '') + 'small_leaf_span'
            key = f'claim-{len(claims)+1:04d}'
            node.set('data-da-element-key', key)
            valid = bool(refs) and all(ref in facts and set(facts[ref].get('sourceSlideIds',[])) <= set(lineage) for ref in refs)
            category = ('presentation_label' if presentation else
                        'verified_source_missing_reference' if mapping and any(method in mapping for method in ('exact_source_text','verified_cover_title')) else
                        'declared_evidence_needs_review' if valid else 'requires_evidence_review')
            item = {'slide':ordinal,'elementKey':key,'text':text,'tag':tag,
                    'classification':category,'originalSourceFactIds':original_refs,
                    'sourceFactIds':refs,'sourcePages':[pages[s] for s in lineage],
                    'sourceEvidence':[{'factId':ref,'text':facts[ref]['text'],'sourcePages':[pages[s] for s in facts[ref].get('sourceSlideIds',[])]} for ref in refs if ref in facts]}
            claims.append(item)
            if mapping or (not presentation and not valid) or (refs and tag not in compiler._GROUNDABLE_TAGS | {'text','tspan','div'}):
                diagnostics.append({**item,'normalization':mapping,
                    'code':('reference_resolved' if category == 'verified_source_missing_reference' else 'grounding_wrapper_normalized') if mapping else 'evidence_link_missing_or_invalid'})
    internal = compiler._serialize(root)
    binding = sha256(json.dumps({'policy':HANDOFF_POLICY,'rawHash':sha256(raw.encode()).hexdigest(),
        'normalizedHash':sha256(internal.encode()).hexdigest(),'facts':context['sourceFacts'],
        'source':context.get('betaSourceDocument')},sort_keys=True).encode()).hexdigest()
    return QuarantinedCandidate(internal, tuple(claims), tuple(diagnostics), len(slides), binding)
