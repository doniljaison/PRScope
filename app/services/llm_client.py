"""
llm_client.py — A dedicated client for interacting with the Anthropic (Claude) API.
"""
import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings

logger = logging.getLogger(__name__)

class LLMParseError(Exception):
    """Raised when the LLM response cannot be parsed as expected."""
    pass

class LLMClient:
    def __init__(self):
        """Initialize the Anthropic client."""
        # The AsyncAnthropic client will automatically use the ANTHROPIC_API_KEY environment variable.
        # Alternatively, we can pass it explicitly.
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY is missing. LLM calls will fail.")
        
        self.client = AsyncAnthropic(api_key=api_key)
        # Using Claude 3.5 Sonnet as recommended
        self.model = "claude-3-5-sonnet-20240620"

    def _build_prompt(self, diff_text: str) -> str:
        """Construct the prompt instructing Claude how to review the code."""
        return f"""You are an expert Senior Software Engineer performing a code review.
Please review the following Pull Request diff and provide constructive, actionable feedback.

Rules:
1. Only comment on actual issues, bugs, or significant improvements (performance, security, readability). Do not leave "nit" comments.
2. If there are no issues, return an empty array.
3. You MUST respond with ONLY a raw JSON array. Do not wrap the JSON in markdown code blocks. Do not include any conversational text before or after the JSON.

The JSON array must contain objects with the following schema:
[
  {{
    "path": "path/to/file.py",
    "line": 15,
    "body": "Your review comment here..."
  }}
]

Here is the diff:
{diff_text}
"""

    async def analyze_diff(self, diff_text: str) -> list[dict[str, Any]]:
        """
        Send the diff to Claude and return a parsed list of review comments.
        """
        if not diff_text or not diff_text.strip():
            logger.info("Diff is empty. Skipping LLM analysis.")
            return []

        prompt = self._build_prompt(diff_text)

        try:
            # We use messages API for Claude 3 models
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0.2, # Low temperature for more deterministic/consistent output
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            raw_text = response.content[0].text.strip()
            logger.debug(f"Raw LLM response: {raw_text}")

            # Strip possible markdown code blocks if the LLM ignores instructions
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()

            comments = json.loads(raw_text)
            
            if not isinstance(comments, list):
                raise LLMParseError("LLM response was JSON but not a list.")
                
            return comments

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise LLMParseError("Invalid JSON from LLM") from e
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            raise
