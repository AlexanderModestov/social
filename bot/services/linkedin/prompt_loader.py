import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SKILLS_ROOT = Path(__file__).resolve().parents[3] / "skills" / "linkedin"

# short key -> vendored directory name
SKILL_DIRS = {
    "post-writer": "linkedin-post-writer",
    "comment-drafter": "linkedin-comment-drafter",
    "reply-handler": "linkedin-reply-handler",
    "humanizer": "linkedin-humanizer",
    "post-audit": "linkedin-humanizer",          # audit is a humanizer mode
    "hook-extractor": "linkedin-hook-extractor",
    "engagement-monitor": "linkedin-engager-analytics",
    "profile-optimizer": "linkedin-profile-optimizer",
    "content-planner": "linkedin-content-planner",
    "employee-advocacy": "linkedin-employee-advocacy",
}

_REF_LINK_RE = re.compile(r"`?((?:\.\./)*references/[\w\-./]+\.md)`?")


def _resolve_ref(root: Path, skill_dir: Path, rel: str) -> Optional[Path]:
    """Resolve a cited reference link to an on-disk file.

    Two citation forms are supported, with explicit intent:
      * ``references/NAME.md`` (skill-local) -> ``<skill_dir>/references/NAME.md``
      * ``../../references/NAME.md`` (root-shared; the ``../`` prefix is an
        upstream-layout artifact) -> ``<root>/references/NAME.md``

    If the intended location is missing, fall back to the root references dir
    keyed on the basename. Returns None if nothing resolves.
    """
    name = rel.split("/")[-1]
    if rel.startswith("../"):
        # Root-shared reference: always resolve under <root>/references.
        intended = root / "references" / name
    else:
        # Skill-local reference.
        intended = skill_dir / rel

    if intended.exists():
        return intended

    # Fallback: root-level references by basename.
    fallback = root / "references" / name
    return fallback if fallback.exists() else None


@lru_cache(maxsize=64)
def _build_static(root_str: str, skill: str) -> str:
    """Assemble the static (ToV-independent) prompt for a skill.

    Process-level cache keyed on ``(root_str, skill)`` so multiple
    SkillPromptLoader instances share results without retaining instances.
    """
    if skill not in SKILL_DIRS:
        raise KeyError(f"unknown skill: {skill}")
    root = Path(root_str)
    skill_dir = root / SKILL_DIRS[skill]
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    voice = (root / "root_voice_rules.md").read_text(encoding="utf-8")

    inlined = []
    for rel in dict.fromkeys(_REF_LINK_RE.findall(skill_md)):  # de-dupe, keep order
        path = _resolve_ref(root, skill_dir, rel)
        if path is None or not path.exists():
            logger.warning("skill %s: unresolved reference %s", skill, rel)
            continue
        body = path.read_text(encoding="utf-8")
        inlined.append(f"\n\n# Reference: {path.name}\n\n{body}")

    # Rewrite the raw relative-link paths in the SKILL.md body to plain
    # reference names so no unresolved "../../references/" link text leaks
    # into the assembled prompt. The actual content is appended below.
    skill_md = _REF_LINK_RE.sub(lambda m: m.group(1).split("/")[-1], skill_md)

    return f"{voice}\n\n# Skill instructions\n\n{skill_md}" + "".join(inlined)


class SkillPromptLoader:
    def __init__(self, root: Path = SKILLS_ROOT):
        self.root = root

    def _static_prompt(self, skill: str) -> str:
        return _build_static(str(self.root), skill)

    def build(self, skill: str, tov: dict) -> str:
        static = self._static_prompt(skill)
        tov_block = json.dumps(tov, indent=2) if tov else "(none provided)"
        return f"{static}\n\n# User tone-of-voice profile\n\n{tov_block}"
