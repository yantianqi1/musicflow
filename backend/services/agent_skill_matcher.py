from dataclasses import dataclass

from backend.models.agent_attachment import AgentAttachment, AgentAttachmentType
from backend.models.agent_session import AgentSessionStatus
from backend.services.agent_skills import SkillDef, SKILL_REGISTRY


@dataclass(frozen=True)
class SkillMatchResult:
    primary_intent: str
    secondary_intents: tuple[str, ...]
    matched_skills: tuple[SkillDef, ...]
    confidence: float


def resolve_skills(
    user_message: str,
    conversation_context: list[dict] | None = None,
    attachments: list[AgentAttachment] | None = None,
    session_status: AgentSessionStatus | None = None,
) -> SkillMatchResult:
    text_pool = (user_message or "").lower()
    if conversation_context:
        for message in conversation_context[-6:]:
            content = message.get("content")
            if isinstance(content, str):
                text_pool += " " + content.lower()

    candidates = []
    for skill in SKILL_REGISTRY.values():
        if skill.always_active or any(keyword in text_pool for keyword in skill.keywords):
            candidates.append(skill)

    attachments = attachments or []
    attachment_kinds = {item.kind for item in attachments}
    if AgentAttachmentType.audio in attachment_kinds:
        candidates.extend(_skills_by_name("voice_management", "speech_synthesis", "music_creation"))
    if AgentAttachmentType.text in attachment_kinds:
        candidates.extend(_skills_by_name("speech_synthesis", "voice_over"))

    if session_status == AgentSessionStatus.awaiting_confirmation:
        candidates.extend(_skills_by_name("billing"))

    deduped = {skill.name: skill for skill in candidates}
    ordered = tuple(sorted(deduped.values(), key=lambda skill: skill.priority, reverse=True))
    primary = ordered[0].name if ordered else "general"
    secondary = tuple(skill.name for skill in ordered[1:3])
    confidence = 0.9 if ordered else 0.2
    return SkillMatchResult(primary, secondary, ordered, confidence)


def _skills_by_name(*names: str) -> list[SkillDef]:
    return [SKILL_REGISTRY[name] for name in names if name in SKILL_REGISTRY]
