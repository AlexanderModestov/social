import logging

import pytest
from bot.services.linkedin.prompt_loader import SkillPromptLoader


def test_loads_skill_and_inlines_references():
    loader = SkillPromptLoader()
    prompt = loader.build("post-writer", tov={"role": "founder"})
    # SKILL.md body present
    assert "LinkedIn Post Writer" in prompt
    # a referenced file got inlined (hook formulas content)
    assert "Platform Risk Anaphora" in prompt
    # global voice rules prepended
    assert "No em dashes" in prompt
    # user ToV injected
    assert "founder" in prompt


def test_no_unresolved_reference_links_remain():
    loader = SkillPromptLoader()
    prompt = loader.build("post-writer", tov={})
    assert "../../references/" not in prompt
    # empty ToV renders the placeholder
    assert "(none provided)" in prompt


def test_unknown_skill_raises():
    with pytest.raises(KeyError):
        SkillPromptLoader().build("does-not-exist", tov={})


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_skill_local_reference_resolves_to_skill_dir(tmp_path, monkeypatch):
    # Make the temp skill resolvable under the short-key map.
    from bot.services.linkedin import prompt_loader as pl

    monkeypatch.setitem(pl.SKILL_DIRS, "post-writer", "linkedin-post-writer")
    pl._build_static.cache_clear()

    _write(tmp_path / "root_voice_rules.md", "VOICE RULES")
    skill_dir = tmp_path / "linkedin-post-writer"
    _write(
        skill_dir / "SKILL.md",
        "# Skill\n\nSee references/local.md and ../../references/shared.md\n",
    )
    # skill-local ref and a DIFFERENT root ref with the same basename collision avoided
    _write(skill_dir / "references" / "local.md", "LOCAL_MARKER")
    _write(tmp_path / "references" / "shared.md", "SHARED_MARKER")

    prompt = SkillPromptLoader(root=tmp_path).build("post-writer", tov={})

    assert "LOCAL_MARKER" in prompt  # skill-local ref resolved to skill dir
    assert "SHARED_MARKER" in prompt  # ../../ ref resolved to root references


def test_unresolved_reference_is_skipped_with_warning(tmp_path, monkeypatch, caplog):
    from bot.services.linkedin import prompt_loader as pl

    monkeypatch.setitem(pl.SKILL_DIRS, "post-writer", "linkedin-post-writer")
    # Clear the process-level cache so the temp root is rebuilt fresh.
    pl._build_static.cache_clear()

    _write(tmp_path / "root_voice_rules.md", "VOICE RULES")
    skill_dir = tmp_path / "linkedin-post-writer"
    _write(
        skill_dir / "SKILL.md",
        "# Skill\n\nSee references/missing.md\n",
    )

    with caplog.at_level(logging.WARNING):
        prompt = SkillPromptLoader(root=tmp_path).build("post-writer", tov={})

    # Build did not crash and the missing file's text is absent.
    assert "VOICE RULES" in prompt
    assert "unresolved reference" in caplog.text
