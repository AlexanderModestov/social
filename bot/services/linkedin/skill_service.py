import json
import anthropic
from bot.config import settings
from bot.services.linkedin.prompt_loader import SkillPromptLoader

# per-skill output budgets
MAX_TOKENS = {
    "content-planner": 4096,
    "employee-advocacy": 4096,
    "profile-optimizer": 3072,
}
DEFAULT_MAX_TOKENS = 2048


class LinkedInSkillService:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.loader = SkillPromptLoader()

    async def run(
        self,
        skill: str,
        user_inputs: dict,
        tov: dict,
        previous: str | None = None,
        feedback: str | None = None,
    ) -> str:
        system = self.loader.build(skill, tov)

        parts = []
        for key, value in user_inputs.items():
            if value:
                label = key.replace("_", " ").upper()
                rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
                parts.append(f"{label}:\n{rendered}")
        if previous and feedback:
            parts.append(f"PREVIOUS OUTPUT:\n{previous}\n\nFEEDBACK:\n{feedback}")

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=MAX_TOKENS.get(skill, DEFAULT_MAX_TOKENS),
            system=system,
            messages=[{"role": "user", "content": "\n\n".join(parts)}],
        )
        return response.content[0].text
