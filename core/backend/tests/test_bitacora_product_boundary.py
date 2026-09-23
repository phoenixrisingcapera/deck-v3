from app.ai.instant_deck_knowledge_context import _load_json_files_from_directory


def test_instant_deck_knowledge_loader_excludes_local_bitacora(tmp_path) -> None:
    (tmp_path / "prompt_recipe.json").write_text(
        '{"defaultPrompt":"Redesign this deck as a VC."}',
        encoding="utf-8",
    )
    (tmp_path / "BITÁCORA.json").write_text(
        '{"privateOperatorNote":"must never reach product context"}',
        encoding="utf-8",
    )
    local_log_directory = tmp_path / "bitacora"
    local_log_directory.mkdir()
    (local_log_directory / "notes.json").write_text(
        '{"privateOperatorNote":"must never enter RAG"}',
        encoding="utf-8",
    )

    modules = _load_json_files_from_directory(tmp_path)

    assert set(modules) == {"prompt_recipe"}
    assert "privateOperatorNote" not in str(modules)
