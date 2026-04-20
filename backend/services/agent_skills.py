"""Agent skill definitions.

Each skill provides a system prompt module that is dynamically loaded
based on user message content. This mirrors the agent_tools.py pattern:
a SKILL_REGISTRY maps skill names to their definition, keywords, and
prompt template.

Usage:
    from backend.services.agent_skills import match_skills, SKILL_REGISTRY

    active = match_skills(user_message, conversation_context)
    prompt_parts = [s.prompt_template for s in active]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SkillDef:
    """A single skill that can be dynamically activated."""

    name: str                                    # unique id, e.g. "voice_over"
    description: str                             # short Chinese description
    keywords: list[str] = field(default_factory=list)  # trigger keywords
    priority: int = 0                            # higher = loaded earlier
    always_active: bool = False                  # True = always included
    prompt_template: str = ""                    # system prompt fragment
    related_tools: list[str] = field(default_factory=list)


SKILL_REGISTRY: dict[str, SkillDef] = {}


def _register(skill: SkillDef):
    SKILL_REGISTRY[skill.name] = skill


def get_skill(name: str) -> SkillDef | None:
    return SKILL_REGISTRY.get(name)


def match_skills(
    user_message: str,
    conversation_context: list[dict] | None = None,
) -> list[SkillDef]:
    """Return skills that should be active for this user message.

    Always-active skills are always included. Others are matched by
    keyword presence in the user message + recent conversation context.
    Results are sorted by priority (descending).
    """
    matched: list[SkillDef] = []

    # Build text pool: current message + last few assistant/user turns
    text_pool = user_message.lower()
    if conversation_context:
        for msg in conversation_context[-6:]:
            content = msg.get("content") or ""
            if isinstance(content, str):
                text_pool += " " + content.lower()

    for skill in SKILL_REGISTRY.values():
        if skill.always_active:
            matched.append(skill)
            continue
        if any(kw in text_pool for kw in skill.keywords):
            matched.append(skill)

    matched.sort(key=lambda s: s.priority, reverse=True)
    logger.debug(
        "Matched skills: %s",
        [s.name for s in matched],
    )
    return matched


# ---------------------------------------------------------------------------
# Import all skill modules to trigger registration
# ---------------------------------------------------------------------------

def _load_all_skills():
    """Import skill modules so they call _register()."""
    from backend.services.skills import (  # noqa: F401
        base,
        music_creation,
        speech_synthesis,
        voice_over,
        voice_management,
        billing,
    )


_load_all_skills()
