import json
import re
from functools import lru_cache
from pathlib import Path

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


class SkillPromptLoader:
    def __init__(self, root: Path = SKILLS_ROOT):
        self.root = root

    @lru_cache(maxsize=32)
    def _static_prompt(self, skill: str) -> str:
        if skill not in SKILL_DIRS:
            raise KeyError(f"unknown skill: {skill}")
        skill_dir = self.root / SKILL_DIRS[skill]
        skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        voice = (self.root / "root_voice_rules.md").read_text(encoding="utf-8")

        inlined = []
        for rel in dict.fromkeys(_REF_LINK_RE.findall(skill_md)):  # de-dupe, keep order
            path = self._resolve_ref(skill_dir, rel)
            if path and path.exists():
                body = path.read_text(encoding="utf-8")
                inlined.append(f"\n\n# Reference: {path.name}\n\n{body}")

        # Rewrite the raw relative-link paths in the SKILL.md body to plain
        # reference names so no unresolved "../../references/" link text leaks
        # into the assembled prompt. The actual content is appended below.
        skill_md = _REF_LINK_RE.sub(lambda m: m.group(1).split("/")[-1], skill_md)

        return f"{voice}\n\n# Skill instructions\n\n{skill_md}" + "".join(inlined)

    def _resolve_ref(self, skill_dir: Path, rel: str) -> Path | None:
        # try skill-local first, then root-level references
        for base in (skill_dir, self.root):
            candidate = (base / rel).resolve()
            if candidate.exists():
                return candidate
        # bare references/x.md under root
        name = rel.split("/")[-1]
        candidate = self.root / "references" / name
        return candidate if candidate.exists() else None

    def build(self, skill: str, tov: dict) -> str:
        static = self._static_prompt(skill)
        tov_block = json.dumps(tov, indent=2) if tov else "(none provided)"
        return f"{static}\n\n# User tone-of-voice profile\n\n{tov_block}"
