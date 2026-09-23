"""Keep SVG text labels on distinct lines without changing their wording.

The API reads available audited offsets and records automatic line flow when needed. The isolated renderer receives only
bounded numeric geometry tied to an existing artifact, never provider markup.
"""
from hashlib import sha256
import re

from sqlalchemy.exc import IntegrityError

from app.db.models import DeckLlmArtifact, InstantDeckProviderAttempt
from app.services.rendering import html_deck_compiler as compiler

POLICY = 'instant-svg-text-offsets.v2'


def _digest(text):
    return sha256(' '.join(text.split()).encode()).hexdigest()


def _lengths(value):
    parts = re.split(r'[\s,]+', value.strip())
    return 1 <= len(parts) <= 64 and all(re.fullmatch(
        r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:px|em|ex|rem|pt|pc|cm|mm|in|%)?', part
    ) for part in parts)


def _sections(root):
    return [n for n in root.iter() if compiler._local_name(n.tag) == 'section'
            and 'deck-section' in n.get('class', '').split()]


def _labels(section):
    for svg_index, svg in enumerate(n for n in section.iter() if compiler._local_name(n.tag) == 'svg'):
        for index, node in enumerate(n for n in svg.iter() if compiler._local_name(n.tag) in {'text', 'tspan'}):
            yield (svg_index, index, compiler._local_name(node.tag)), node


def extract_offsets(raw, sanitized):
    original = _sections(compiler._parse_document(compiler._strip_provider_fence(raw)))
    saved = _sections(compiler._parse_document(sanitized))
    if len(original) != len(saved):
        return []
    rows = []
    for source, target in zip(original, saved):
        originals = dict(_labels(source))
        for address, node in _labels(target):
            prior = originals.get(address)
            if prior is None or _digest(''.join(prior.itertext())) != _digest(''.join(node.itertext())):
                continue
            # Existing absolute coordinates must agree, as well as claim text.
            if any(prior.get(a) != node.get(a) for a in ('x', 'y')):
                continue
            offsets = {a: prior.get(a) for a in ('dx', 'dy')
                       if prior.get(a) is not None and node.get(a) is None and _lengths(prior.get(a))}
            if offsets:
                rows.append({'sectionId': target.get('data-da-slide-root'), 'address': list(address),
                             'textHash': _digest(''.join(node.itertext())), 'offsets': offsets})
    return rows[:512]


def apply_offsets(document, rows):
    root = compiler._parse_document(document)
    lookup = {(row['sectionId'], tuple(row['address'])): row for row in rows}
    for section in _sections(root):
        for address, node in _labels(section):
            row = lookup.get((section.get('data-da-slide-root'), address))
            if not row or row['textHash'] != _digest(''.join(node.itertext())):
                continue
            for attr, value in row['offsets'].items():
                if attr in {'dx', 'dy'} and isinstance(value, str) and _lengths(value) and node.get(attr) is None:
                    node.set(attr, value)
    return '<!doctype html>\n' + compiler._serialize(root)


def missing_line_offsets(document):
    """Lay out separate labels that explicitly reset x but have no line offset."""
    rows = []
    for section in _sections(compiler._parse_document(document)):
        addresses = {id(node): address for address, node in _labels(section)}
        for text in section.iter():
            if text.tag != compiler._SVG_NS + 'text':
                continue
            previous = None
            for node in text:
                if node.tag != compiler._SVG_NS + 'tspan':
                    previous = None
                    continue
                if (previous is not None and node.get('x') is not None
                    and node.get('x') == previous.get('x')
                    and node.get('y') is None and node.get('dy') is None
                    and _digest(''.join(node.itertext())) != _digest(''.join(previous.itertext()))):
                    rows.append({'sectionId': section.get('data-da-slide-root'),
                                 'address': list(addresses[id(node)]),
                                 'textHash': _digest(''.join(node.itertext())),
                                 'offsets': {'dy': '1.4em'}, 'method': 'automatic_line_flow'})
                previous = node
    return rows[:512]


def _identity(artifact):
    return 'svglayout_' + sha256((POLICY + '::' + artifact.id + ':' + artifact.content_hash).encode()).hexdigest()[:24]


def ensure_saved_offsets(db, compilation, artifact, read_document):
    if compilation.compiler_version != compiler.SVG_TEXT_LAYOUT_COMPILER_VERSION:
        return
    if (compilation.manifest_json or {}).get('evidencePolicy') != 'advisory-draft.v1':
        return
    identity = _identity(artifact)
    if db.get(DeckLlmArtifact, identity) is not None:
        return
    status, rows, source_hash = 'unavailable', [], None
    document = read_document(artifact)
    try:
        from app.services.llm.full_html_generation_service import _repair_checkpoint_raw
        attempt = db.get(InstantDeckProviderAttempt, compilation.provider_attempt_id)
        if attempt is not None and attempt.id == artifact.provider_attempt_id:
            raw = _repair_checkpoint_raw(db, attempt, expected_deck_id=artifact.deck_id)
            source_hash = sha256(raw.encode()).hexdigest()
            rows = extract_offsets(raw, document)
            status = 'completed'
    except Exception:
        pass  # Expired historical checkpoints leave the usable baseline intact.
    rows += missing_line_offsets(apply_offsets(document, rows))
    if rows:
        status = 'completed'
    row = DeckLlmArtifact(id=identity, deck_id=artifact.deck_id, artifact_type=POLICY,
        artifact_key=identity, schema_version=POLICY, status=status,
        payload_json={'artifactId': artifact.id, 'artifactHash': artifact.content_hash,
                      'designVersionId': artifact.design_version_id, 'sourceHash': source_hash,
                      'offsets': rows, 'layoutPolicy': 'svg-multiline-flow.v1', 'factualVerification': 'unchanged'})
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        pass  # Concurrent preview requests share the immutable repair record.


def restore_saved_offsets(db, artifact, document):
    row = db.get(DeckLlmArtifact, _identity(artifact))
    payload = (row.payload_json or {}) if row else {}
    if (row is None or row.deck_id != artifact.deck_id or row.status != 'completed'
        or payload.get('artifactHash') != artifact.content_hash
        or payload.get('designVersionId') != artifact.design_version_id):
        return document
    return apply_offsets(document, payload.get('offsets') or [])
