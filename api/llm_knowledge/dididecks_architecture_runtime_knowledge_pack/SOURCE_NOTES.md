# Source Notes

This package was synthesized from the DidiDecks / DeckAiStack architecture discussion and uploaded reference notes.

Key ideas incorporated:

- DidiDecks should be a database-backed interactive deck editor, not a static slide generator.
- The differentiator is persistent business fields and reusable slide components, not only free-floating visual objects.
- The frontend must remain separate from backend persistence, auth, billing, exports, AI commands, and guardrails.
- The editor must connect to the same block/persistent-field model as Deck Map, Smart Edit, and Rebuild.
- Repository verification should detect architecture drift, not only build failures.
