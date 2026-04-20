from backend.models.agent_session import AgentSession
from backend.models.user import User
from backend.services.agent_attachments import summarize_attachments
from backend.services.agent_skill_matcher import SkillMatchResult
from backend.services.agent_tools import TOOL_REGISTRY
from backend.services.billing_service import estimate_cost
from backend.services import voice_service
from backend.services.voice_casting import format_voice_list_for_prompt


_VOICE_RELEVANT_SKILLS = {"speech_synthesis", "voice_management", "voice_over"}


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


async def _build_relevant_pricing(db, matched_skills: SkillMatchResult) -> str:
    tool_names = []
    for skill in matched_skills.matched_skills:
        tool_names.extend(skill.related_tools)
    if not tool_names:
        return "无相关价格信息"

    lines = []
    seen = set()
    for tool_name in tool_names:
        if tool_name in seen or tool_name not in TOOL_REGISTRY:
            continue
        seen.add(tool_name)
        tool = TOOL_REGISTRY[tool_name]
        if not tool.service_type:
            lines.append(f"- {tool_name}: 免费")
            continue
        if tool.available_models:
            for model in tool.available_models:
                cost = await estimate_cost(db, tool.service_type, model["id"])
                unit = model.get("unit", "积分/次")
                lines.append(f"- {tool_name} [{model['name']}]: {cost} {unit}")
            continue
        cost = await estimate_cost(db, tool.service_type)
        lines.append(f"- {tool_name}: {cost} 积分/次")
    return "\n".join(lines)


async def build_prompt(
    db,
    user: User,
    session: AgentSession,
    matched_skills: SkillMatchResult,
    attachments,
    active_tool_call,
) -> tuple[str, list[str]]:
    relevant_pricing = await _build_relevant_pricing(db, matched_skills)
    runtime_context = "\n".join([
        f"当前会话状态: {session.status.value}",
        f"余额: 充值 {user.credits}, 签到 {user.free_credits}",
        f"活动工具: {active_tool_call.tool_name if active_tool_call else '无'}",
        "附件摘要:",
        summarize_attachments(attachments),
    ])

    format_ctx = _SafeFormatDict({
        "credits": user.credits,
        "free_credits": user.free_credits,
        "pricing_summary": relevant_pricing,
    })

    skill_chunks = [
        skill.prompt_template.format_map(format_ctx)
        for skill in matched_skills.matched_skills
    ]

    sections = [
        "## 运行时上下文",
        runtime_context,
        "## 技能指引",
        "\n\n".join(skill_chunks),
    ]

    voice_relevant = any(
        s.name in _VOICE_RELEVANT_SKILLS for s in matched_skills.matched_skills
    )
    if voice_relevant:
        voice_list = await _build_prompt_voice_list()
        sections.append(
            "## 可用音色列表\n"
            + voice_list
            + "\n\n如需更多音色或不确定，再调用 list_voices 查询。"
        )

    prompt = "\n\n".join(sections)
    return prompt, [
        skill.description for skill in matched_skills.matched_skills if not skill.always_active
    ]


async def _build_prompt_voice_list() -> str:
    try:
        voices = (await voice_service.list_voices(voice_type="all")).get("voices", [])
    except Exception:
        voices = []
    return format_voice_list_for_prompt(voices)
