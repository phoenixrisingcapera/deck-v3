"""MVP policy changes new commands while retaining historical general replay."""
from types import SimpleNamespace
from app.services.llm.instant_deck_context_builder import resolve_instant_deck_intent
from app.services.llm import full_html_generation_service as html
from app.services.deck_processing.workflow_orchestration import UPLOAD_FIRST_INSTANT_DECK_PROMPT
from test_instant_deck_art_direction_contract import _deck


def test_mvp_audience_is_application_owned_and_historical_general_stays_decodable():
    from app.services.llm.instant_deck_mvp_policy import MVP_AUDIENCE
    deck = SimpleNamespace(title='Company deck', purpose='Source purpose', audience='General audience')
    slides = [SimpleNamespace(raw_text='Company operating evidence')]
    for audience, requested_type in [(None, None), ('Students', 'educational'), ('Buyers', 'sales'), ('Investors', 'investor_pitch')]:
        assert resolve_instant_deck_intent(deck=deck, selected_slides=slides, audience=audience, deck_type=requested_type, user_goal='Change the audience') == (MVP_AUDIENCE, 'investor_pitch')
    assert 'investor evaluation' in UPLOAD_FIRST_INSTANT_DECK_PROMPT
    # Persisted historical requests continue using their original prompt and intent.
    raw = _deck(visuals=3).replace('people-proof', 'comparison').replace('capital-plan', 'architecture').replace('</main>', '<section class="deck-section" data-layout-intent="closing" data-composition-family="timeline" data-slot-title="Next steps"><h2>Next steps</h2></section></main>')
    html.validate_full_html_presentation_quality(raw, system_prompt_version='full-html-system-prompt.v38', context_pack={'presentationIntent':'general','sourceDocumentPageCount':7})
