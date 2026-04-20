from __future__ import annotations

import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


ROLE_CANDIDATE_LIMIT = 3
NARRATION_ROLES = {"旁白", "叙述者", "narrator", "旁白/叙述"}

_FALLBACK_VOICE_LIST = """\
### 系统音色
旁白/叙述: male-qn-jingying(精英青年), male-qn-qingse(青涩青年), female-chengshu(成熟女性), presenter_male(男播音), presenter_female(女播音), audiobook_male_1(有声书男声), audiobook_male_2(有声书男声2), audiobook_female_1(有声书女声)
青年男性: male-qn-qingse(青涩), male-qn-jingying(精英), male-qn-badao(霸道), male-qn-daxuesheng(大学生)
女性: female-shaonv(少女), female-yujie(御姐), female-chengshu(成熟), female-tianmei(甜美)
特殊: clever_boy(机灵男孩), cute_boy(可爱男孩), lovely_girl(可爱女孩), Santa_Claus(圣诞老人)
Beta高质量版: 上述音色加 -jingpin 后缀，如 male-qn-jingying-jingpin"""


def format_voice_list_for_prompt(voices: list[dict]) -> str:
    if not voices:
        return _FALLBACK_VOICE_LIST

    system_voices = []
    custom_voices = []
    for voice in voices:
        label = _voice_label(voice)
        if voice.get("description"):
            label = f"{label} - {voice['description'][:30]}"
        if voice.get("voice_type") == "system":
            system_voices.append(label)
            continue
        voice_type = "克隆" if voice.get("voice_type") == "cloned" else "AI设计"
        custom_voices.append(f"{label} [{voice_type}]")

    parts = []
    if system_voices:
        parts.append("### 系统音色\n" + ", ".join(system_voices))
    if custom_voices:
        parts.append("### 用户自定义音色（优先考虑使用）\n" + ", ".join(custom_voices))
    else:
        parts.append("### 用户自定义音色\n（暂无，用户可通过克隆或AI设计创建专属音色）")
    return "\n\n".join(parts)


def build_voice_selection(segments: list[dict], voices: list[dict], candidate_limit: int = ROLE_CANDIDATE_LIMIT) -> dict:
    grouped_roles = _group_role_segments(segments)
    catalog = [_normalize_voice(voice) for voice in voices]
    roles = []
    for role_name, role_segments in grouped_roles.items():
        profile = _infer_role_profile(role_name, role_segments)
        current_voice_id = _pick_current_voice_id(role_segments)
        candidates = _pick_candidates(profile, catalog, current_voice_id, candidate_limit)

        if not candidates and not current_voice_id:
            default_vid = (
                "audiobook_male_1" if "narrator" in profile["traits"]
                else "male-qn-qingse"
            )
            logger.warning(
                "Voice catalog empty for role %r; falling back to default %s",
                role_name, default_vid,
            )
            candidates = [{
                "voice_id": default_vid,
                "voice_name": default_vid,
                "intro": "系统默认（音色目录暂不可用）",
                "score": 0,
                "reason": "音色服务暂时不可用，使用默认值",
            }]

        roles.append({
            "role": role_name,
            "role_summary": profile["summary"],
            "selected_voice_id": candidates[0]["voice_id"] if candidates else current_voice_id,
            "current_voice_id": current_voice_id,
            "line_count": len(role_segments),
            "sample_text": role_segments[0].get("text", "")[:80],
            "candidates": candidates,
        })
    return {"candidate_limit": candidate_limit, "roles": roles}


def enrich_batch_voice_over_params(tool_params: dict, voices: list[dict], candidate_limit: int = ROLE_CANDIDATE_LIMIT) -> dict:
    enriched = dict(tool_params)
    segments = list(tool_params.get("segments", []))
    voice_selection = build_voice_selection(segments, voices, candidate_limit)
    enriched["voice_selection"] = voice_selection
    enriched["segments"] = apply_role_voice_selection(segments, voice_selection)
    return enriched


def apply_role_voice_selection(segments: list[dict], voice_selection: dict | None) -> list[dict]:
    if not voice_selection:
        return segments
    selected_map = {
        role["role"]: role["selected_voice_id"]
        for role in voice_selection.get("roles", [])
        if role.get("selected_voice_id")
    }
    if not selected_map:
        return segments
    updated = []
    for segment in segments:
        role_name = segment.get("role")
        voice_id = selected_map.get(role_name)
        if not voice_id:
            updated.append(dict(segment))
            continue
        updated.append({**segment, "voice_id": voice_id})
    return updated


def _group_role_segments(segments: list[dict]) -> OrderedDict[str, list[dict]]:
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for segment in segments:
        role_name = (segment.get("role") or "").strip()
        if not role_name:
            continue
        grouped.setdefault(role_name, []).append(segment)
    return grouped


def _pick_current_voice_id(role_segments: list[dict]) -> str | None:
    for segment in role_segments:
        voice_id = segment.get("voice_id")
        if voice_id:
            return voice_id
    return None


def _normalize_voice(voice: dict) -> dict:
    voice_id = voice.get("voice_id", "")
    voice_name = voice.get("voice_name") or voice_id
    searchable = " ".join(filter(None, [voice_id, voice_name, voice.get("description", "")])).lower()
    traits = _extract_traits(searchable)
    if _is_mandarin_voice_id(voice_id.lower()):
        traits.add("mandarin")
    return {
        "voice_id": voice_id,
        "voice_name": voice_name,
        "voice_type": voice.get("voice_type", "system"),
        "searchable": searchable,
        "traits": traits,
        "intro": _build_intro(traits, voice_name),
    }


def _infer_role_profile(role_name: str, role_segments: list[dict]) -> dict:
    normalized = role_name.strip().lower()
    current_voice = _pick_current_voice_id(role_segments) or ""
    searchable = f"{role_name} {current_voice}".lower()
    if role_name in NARRATION_ROLES or "旁白" in normalized or "叙述" in normalized:
        traits = {"narrator"}
        if _is_chinese_context(role_name, current_voice):
            traits.add("mandarin")
        return {"summary": "旁白/叙述", "traits": traits}

    traits = set()
    if _is_chinese_context(role_name, current_voice):
        traits.add("mandarin")
    if _contains_any(searchable, ["老", "伯", "爷", "翁", "婆", "奶", "姥", "叔", "婶", "elder", "senior", "antie"]):
        traits.add("elder")
    if _contains_any(searchable, ["少", "青年", "学生", "弟", "妹", "girl", "boy", "youth", "qingse", "daxuesheng"]):
        traits.add("youth")
    if _contains_any(searchable, ["孩", "童", "娃", "cute_boy", "lovely_girl", "clever_boy"]):
        traits.add("child")
    if _contains_any(searchable, ["先生", "师父", "掌柜", "老板", "医生", "老师", "gentleman", "announcer"]):
        traits.add("mature")
    if _contains_any(searchable, ["爷", "伯", "叔", "公", "男", "male", "boy", "gentleman"]):
        traits.add("male")
    if _contains_any(searchable, ["姐", "娘", "婶", "姑", "婆", "女", "female", "girl", "lady", "woman"]):
        traits.add("female")

    summary = "成年角色"
    if "elder" in traits:
        summary = "老年角色"
    elif "child" in traits:
        summary = "儿童角色"
    elif "youth" in traits:
        summary = "青年角色"
    elif "mature" in traits:
        summary = "成熟角色"
    return {"summary": summary, "traits": traits}


def _pick_candidates(profile: dict, catalog: list[dict], current_voice_id: str | None, candidate_limit: int) -> list[dict]:
    candidate_pool = _candidate_pool(catalog, profile["traits"], candidate_limit)
    candidates = sorted(
        (_candidate_entry(voice, profile, current_voice_id) for voice in candidate_pool),
        key=lambda item: (-item["score"], item["voice_id"]),
    )
    deduped = _dedupe_candidates(candidates)

    # Pin the LLM/user-confirmed voice at position 0 so `selected_voice_id`
    # (which reads candidates[0]) reflects the choice already agreed in chat,
    # not the heuristic's top pick. Others remain as alternatives to switch to.
    if current_voice_id:
        idx = next(
            (i for i, item in enumerate(deduped) if item["voice_id"] == current_voice_id),
            None,
        )
        if idx is not None and idx != 0:
            picked = deduped.pop(idx)
            deduped.insert(0, picked)
        elif idx is None:
            catalog_entry = next(
                (voice for voice in catalog if voice["voice_id"] == current_voice_id),
                None,
            )
            if catalog_entry is not None:
                deduped.insert(0, _candidate_entry(catalog_entry, profile, current_voice_id))
            else:
                deduped.insert(0, _fallback_current_candidate(current_voice_id, profile))

    return deduped[:candidate_limit]


def _candidate_pool(catalog: list[dict], role_traits: set[str], candidate_limit: int) -> list[dict]:
    if "mandarin" not in role_traits:
        return catalog
    mandarin_voices = [voice for voice in catalog if "mandarin" in voice["traits"]]
    if len(mandarin_voices) >= candidate_limit:
        return mandarin_voices
    return catalog


def _candidate_entry(voice: dict, profile: dict, current_voice_id: str | None) -> dict:
    return {
        "voice_id": voice["voice_id"],
        "voice_name": voice["voice_name"],
        "intro": voice["intro"],
        "score": _score_voice(voice["voice_id"], voice["traits"], profile["traits"], current_voice_id),
        "reason": _build_reason(voice["traits"], profile["summary"]),
    }


def _score_voice(voice_id: str, voice_traits: set[str], role_traits: set[str], current_voice_id: str | None) -> int:
    score = 0
    if "narrator" in role_traits:
        score += 120 if "narrator" in voice_traits else -20
    if "elder" in role_traits:
        score += 100 if "elder" in voice_traits else 0
        score -= 40 if "youth" in voice_traits else 0
    if "youth" in role_traits:
        score += 80 if "youth" in voice_traits else 0
        score -= 35 if "elder" in voice_traits else 0
    if "child" in role_traits:
        score += 90 if "child" in voice_traits else -20
    if "mature" in role_traits:
        score += 55 if "mature" in voice_traits or "narrator" in voice_traits else 0
    if "mandarin" in role_traits:
        score += 45 if "mandarin" in voice_traits else -20
    if "male" in role_traits and "male" in voice_traits:
        score += 25
    if "male" in role_traits and "female" in voice_traits:
        score -= 30
    if "female" in role_traits and "female" in voice_traits:
        score += 25
    if "female" in role_traits and "male" in voice_traits:
        score -= 30
    if role_traits.isdisjoint({"male", "female"}):
        score += 10 if "narrator" in voice_traits or "mature" in voice_traits else 0
    if current_voice_id and voice_id == current_voice_id:
        score += 18
    return score


def _dedupe_candidates(candidates: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for candidate in candidates:
        voice_id = candidate["voice_id"]
        if voice_id in seen:
            continue
        seen.add(voice_id)
        result.append(candidate)
    return result


def _fallback_current_candidate(current_voice_id: str, profile: dict) -> dict:
    traits = _extract_traits(current_voice_id.lower())
    return {
        "voice_id": current_voice_id,
        "voice_name": current_voice_id,
        "intro": _build_intro(traits, current_voice_id),
        "score": _score_voice(current_voice_id, traits, profile["traits"], current_voice_id),
        "reason": "保留当前方案，便于直接对比",
    }


def _voice_label(voice: dict) -> str:
    voice_id = voice.get("voice_id", "")
    voice_name = voice.get("voice_name") or voice_id
    if voice_name == voice_id:
        return voice_id
    return f"{voice_id}({voice_name})"


def _extract_traits(searchable: str) -> set[str]:
    traits = set()
    if _contains_any(searchable, ["announcer", "radio_host", "news_anchor", "narrator", "audiobook", "presenter", "播报", "主播", "旁白", "叙述"]):
        traits.add("narrator")
    if _contains_any(searchable, ["elder", "senior", "antie", "kind-hearted_elder", "humorous_elder", "大爷", "奶奶", "花甲", "老人"]):
        traits.add("elder")
    if _contains_any(searchable, ["child", "cute_boy", "lovely_girl", "clever_boy", "男童", "女童", "儿童"]):
        traits.add("child")
    if _contains_any(searchable, ["qingse", "daxuesheng", "youth", "shaonv", "teen", "少年", "青年", "少女", "学姐", "学弟"]):
        traits.add("youth")
    if _contains_any(searchable, ["mature", "chengshu", "yujie", "gentleman", "wise", "teacher", "lady", "woman", "成熟", "御姐", "温润", "阅历"]):
        traits.add("mature")
    if _contains_any(searchable, ["male", "boy", "man", "gentleman", "男", "叔", "爷"]):
        traits.add("male")
    if _contains_any(searchable, ["female", "girl", "woman", "lady", "女", "姐", "妹", "奶"]):
        traits.add("female")
    return traits


def _build_intro(traits: set[str], voice_name: str) -> str:
    if "narrator" in traits:
        return "播报感更稳，适合旁白和叙述"
    if "elder" in traits:
        return "老年感明显，适合长辈或店家"
    if "child" in traits:
        return "稚气更强，适合孩童角色"
    if "youth" in traits:
        return "年轻感更强，适合少年或青年"
    if "mature" in traits:
        return "成熟稳定，适合老师或成人人物"
    return f"{voice_name}，可作为当前角色备选"


def _build_reason(traits: set[str], summary: str) -> str:
    if "narrator" in traits:
        return f"更贴近{summary}的叙述感"
    if "elder" in traits:
        return f"更贴近{summary}的年长气质"
    if "youth" in traits:
        return f"更贴近{summary}的年轻感"
    if "mature" in traits:
        return f"更贴近{summary}的稳定感"
    return f"可作为{summary}的对比方案"


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_chinese_context(role_name: str, current_voice_id: str) -> bool:
    searchable = f"{role_name} {current_voice_id}".lower()
    return _has_cjk(role_name) or _is_mandarin_voice_id(searchable)


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _is_mandarin_voice_id(text: str) -> bool:
    return _contains_any(text, ["male-qn", "female-", "audiobook", "presenter", "chinese (mandarin)"])
