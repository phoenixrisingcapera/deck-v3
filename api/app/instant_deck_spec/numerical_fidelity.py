"""Fail-closed company-number authority for the investor production adapter.

Numerical copy is an exact evidence quotation, not a bag of allowlisted digits.
Whitespace is the only permitted normalization. Historical planners are unchanged.
"""
from dataclasses import dataclass
import re

# Preserve the complete lexical quantity. Never use a float for emitted values.
NUMBER = re.compile(r"(?<!\w)(?:[A-Z]{3}\s+|[$€£¥₹]\s*)?[+−-]?(?:\d{1,3}(?:[,\u00a0]\d{3})+|\d+)(?:[.,]\d+)?(?:\s?(?:%|[kKmMbB](?!\w)|million\b|billion\b|trillion\b))?\+?", re.UNICODE)
WORDS = re.compile(r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|trillion|half|quarter|double|triple)\b", re.I)


def normalized(text):
    return " ".join(str(text or "").split())


def has_quantity(text):
    return bool(re.search(r"\d", text or "") or WORDS.search(text or ""))


@dataclass(frozen=True)
class NumericalIssue:
    code: str
    path: str


class NumericalFidelityError(ValueError):
    def __init__(self, code, path):
        self.issues = [NumericalIssue(code, path)]
        super().__init__(f"{code} at {path}")


def exact_metric_claim(number, package, context, aliases, *, compact=True):
    references = {r.reference_id: r for r in package.source_references}
    claims = {normalized(references[r].quoted_text) for r in number.source_reference_ids if references[r].quoted_text}
    if len(claims) != 1:
        raise NumericalFidelityError("numerical_evidence_ambiguous", number.number_id)
    claim = claims.pop()
    # A match must be a full lexical quantity (120 cannot select 1200).
    if number.exact_text not in [m.group() for m in NUMBER.finditer(claim)]:
        raise NumericalFidelityError("numerical_value_not_exact", number.number_id)
    fact_ids = aliases['evidence'][number.number_id]
    facts = {f['factId']: f for f in context['sourceFacts']}
    if not fact_ids or any(facts[f].get('confidence', 'high') != 'high' for f in fact_ids):
        raise NumericalFidelityError("numerical_evidence_unverified", number.number_id)
    if not any(normalized(facts[f]['text']) == claim for f in fact_ids):
        raise NumericalFidelityError("numerical_evidence_changed", number.number_id)
    # The recovered display contract has a bounded context. Do not truncate an
    # amount's qualification to fit it; choose ordinary exact source copy instead.
    if compact and len(claim) > 120:
        raise NumericalFidelityError("numerical_context_exceeds_metric_layout", number.number_id)
    return claim


def validate_plan_numbers(plan, package, context, aliases, *, presentation_policy=None):
    facts = {f['factId']: f for f in context['sourceFacts']}
    def check(text, refs, path, slide=None):
        if not text or not has_quantity(text):
            return
        ids = {f for ref in refs for f in aliases['evidence'][ref]}
        # Full source statement equality retains period, qualifiers, units and
        # meaning. A value appearing elsewhere in the source is not support.
        supporting = [facts[f] for f in ids if normalized(facts[f]['text']) == normalized(text)]
        if not supporting:
            if (presentation_policy == PRESENTATION_POLICY and slide is not None
                    and _source_bound_step_count(text, slide, [facts[f] for f in ids])):
                return
            raise NumericalFidelityError('numerical_claim_not_exact', path)
        if any(f.get('confidence', 'high') != 'high' for f in supporting):
            raise NumericalFidelityError('numerical_evidence_unverified', path)
    all_refs = list(aliases['evidence'])
    check(plan.deck_title, all_refs, 'deck_title')
    for i, slide in enumerate(plan.slides):
        prefix = f'slides[{i}]'
        for key in ['headline', 'subhead', 'narrative_job', 'audience_claim', 'consequence']:
            check(getattr(slide, key), slide.selected_evidence_ids, prefix + '.' + key, slide=slide)
        for j, row in enumerate(slide.body):
            check(row.text, row.evidence_ids, f'{prefix}.body[{j}].text')
        for kind, fields in [('items', ['label', 'detail', 'value', 'group']), ('steps', ['label', 'detail']), ('people', ['name', 'role', 'proof']), ('edges', ['label'])]:
            for j, row in enumerate(getattr(slide.visual, kind)):
                for key in fields:
                    check(getattr(row, key), row.evidence_ids, f'{prefix}.visual.{kind}[{j}].{key}')


PRESENTATION_POLICY = 'source-linked-labels.v1'


def metric_presentation(number, package, context, aliases):
    """Separate a source-derived caption from its complete evidence.

    A line is a label candidate, never a replacement for the full statement.
    Ambiguous/repeated values and long labels use the source-detail composition;
    the app must not select one occurrence or truncate qualifiers to make a card.
    """
    claim = exact_metric_claim(number, package, context, aliases, compact=False)
    references = {r.reference_id: r for r in package.source_references}
    raw = next(references[r].quoted_text for r in number.source_reference_ids if references[r].quoted_text)
    candidates = []
    for line in raw.splitlines():
        matches = [m for m in NUMBER.finditer(line) if m.group() == number.exact_text]
        for match in matches:
            # Keep the rest of the original line, including dates and units.
            label = normalized(line[:match.start()] + line[match.end():]).strip(' .:;—–-')
            candidates.append(label)
    usable = len(candidates) == 1 and 0 < len(candidates[0]) <= 80 and bool(re.search(r'[A-Za-z]', candidates[0]))
    return {'value': number.exact_text, 'label': candidates[0] if usable else None,
            'sourceStatement': claim, 'composition': 'metric' if usable else 'source-detail'}


def _source_bound_step_count(text, slide, supporting):
    """Allow a presentation count only for a matching, evidenced numbered list.

    This is a count of displayed stages, not a derived company quantity. Every
    displayed stage must match the corresponding source item; arbitrary visual
    node counts and ungrounded 'three steps' language do not qualify.
    """
    steps = slide.visual.steps
    count = len(steps)
    if not steps or not 1 <= count <= 12:
        return False
    counted = re.findall(r'(?<![\w$€£])([1-9]\d*)[\s\-‑–]+step(?:s)?\b', text, re.I)
    if counted != [str(count)]:
        return False
    residue = re.sub(r'(?<![\w$€£])([1-9]\d*)[\s\-‑–]+step(?:s)?\b', '', text, flags=re.I)
    if has_quantity(residue):
        return False
    for fact in supporting:
        if fact.get('confidence', 'high') != 'high':
            continue
        items = re.findall(r'^\s*(\d+)[.)]\s*(.+)$', fact['text'], re.M)
        if [int(i) for i, _ in items] != list(range(1, count + 1)):
            continue
        if all(normalized(item).casefold().startswith(normalized(step.label).casefold())
               for (_, item), step in zip(items, steps)):
            return True
    return False
