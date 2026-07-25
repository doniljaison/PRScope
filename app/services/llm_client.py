"""Claude LLM client — sends PR diffs for AI code review."""

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings
from app.core.exceptions import LLMParseError

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY is missing. LLM calls will fail.")
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

    def _build_prompt(self, diff_text: str) -> str:
        return f"""You are an expert Senior Software Engineer performing a code review.
Please review the following Pull Request diff and provide constructive, actionable feedback.

Rules:
1. Only comment on actual issues, bugs, or significant improvements. No nit-picks.
2. If there are no issues, return an empty array.
3. Respond with ONLY a raw JSON array. No markdown code blocks, no conversational text.

Schema:
[
  {{
    "path": "path/to/file.py",
    "line": 15,
    "body": "Your review comment here...",
    "severity": "warning"
  }}
]

Here is the diff:
{diff_text}
"""

    async def analyze_diff(self, diff_text: str) -> list[dict[str, Any]]:
        """Send diff to Claude, return parsed review comments."""
        if not diff_text or not diff_text.strip():
            return []

        prompt = self._build_prompt(diff_text)

        try:
            response = await self.client.messages.create(
                model=self.model, max_tokens=2048, temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.content[0].text.strip()

            # Strip markdown code fences if the LLM ignores instructions
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()

            comments = json.loads(raw_text)
            if not isinstance(comments, list):
                raise LLMParseError("LLM response was JSON but not a list.")
            return comments

        except json.JSONDecodeError as e:
            raise LLMParseError("Invalid JSON from LLM") from e
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            raise
