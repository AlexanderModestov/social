import json
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
    assert "This file moved" not in prompt


def test_unknown_skill_raises():
    with pytest.raises(KeyError):
        SkillPromptLoader().build("does-not-exist", tov={})
