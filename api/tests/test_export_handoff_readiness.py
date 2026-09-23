from types import SimpleNamespace

from app.services.rendering import export_service


class _Query:
    def __init__(self, value):
        self.value = value
    def filter(self, *_args, **_kwargs):
        return self
    def with_for_update(self, **_kwargs):
        return self
    def one_or_none(self):
        return self.value


class _Db:
    def __init__(self, value):
        self.value = value
        self.commits = 0
    def query(self, *_args):
        return _Query(self.value)
    def commit(self):
        self.commits += 1
    def rollback(self):
        raise AssertionError("valid database handoff must commit")


def test_authenticated_html_export_is_ready_when_optional_admin_mirror_fails(monkeypatch):
    deck_export = SimpleNamespace(
        id="export-1", deck_id="deck-1", type=export_service.FINAL_DECK_EXPORT_TYPE,
        content="<!doctype html><html></html>", handoff_status="pending",
        handoff_attempts=0, handoff_attempted_at=None, handoff_error=None,
        handoff_ready_at=None,
    )
    monkeypatch.setattr(export_service, "_metadata_from_content", lambda _export: ("design-1", "html"))
    monkeypatch.setattr(export_service, "_admin_release_directory", lambda _export: "/tmp/not-created")
    monkeypatch.setattr(export_service, "_write_admin_release_package", lambda _export: (_ for _ in ()).throw(OSError("mirror unavailable")))
    db = _Db(deck_export)
    assert export_service.publish_export_handoff(db, deck_export.id) is True
    assert deck_export.handoff_status == "ready"
    assert deck_export.handoff_ready_at is not None
    assert "authenticated export remains ready" in deck_export.handoff_error
    assert db.commits == 1
