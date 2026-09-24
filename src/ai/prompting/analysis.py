"""Prompt construction for profile-driven content analysis."""

from ...models import ContentItem
from ...processing.profiles import LoadedProfile
from .common import EVIDENCE_RULES, UNTRUSTED_INPUT_RULE

ANALYSIS_RULES = f"""You are a content curator evaluating an item under the supplied processing profile.

- {UNTRUSTED_INPUT_RULE}
- Base the analysis only on the supplied item and its metadata.
{EVIDENCE_RULES}
- Apply the profile's evaluation policy consistently.
- This is a high-recall first pass. Prefer relevance recall over precision: when
  an item may have financial-market, listed-company, macroeconomic, AI,
  semiconductor, energy, regulatory, or second-order investment implications,
  retain it as relevant or uncertain rather than dismissing it.
- Set obvious_noise=true only for unmistakably irrelevant entertainment,
  lifestyle, local-crime, spam, or other content with no plausible investment,
  macro, industry, or AI significance."""


def analysis_system_prompt(profile: LoadedProfile) -> str:
    return f"""{ANALYSIS_RULES}

# Profile policy

{profile.analysis_prompt}

# Output contract

Return valid JSON only:
{{
  "score": <number from 0 to 10>,
  "reason": "<concise explanation>",
  "summary": "<one-sentence summary>",
  "tags": ["<tag>", "..."],
  "relevance": "relevant | uncertain | irrelevant",
  "obvious_noise": <boolean>
}}"""


def analysis_user_prompt(
    item: ContentItem,
    content_section: str,
    discussion_section: str,
) -> str:
    return f"""Analyze the following content.

Title: {item.title}
Source: {item.source_type.value}
Author: {item.author or "Unknown"}
URL: {item.url}
{content_section}
{discussion_section}"""
