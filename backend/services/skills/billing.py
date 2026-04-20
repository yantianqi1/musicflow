"""Billing skill — activated only when user explicitly asks about money.

base.py already owns the pricing table. This skill is a thin advisor for pure
pricing queries ("X 多少钱？"、"够不够付？"). Do NOT duplicate the price list.
"""

from backend.services.agent_skills import SkillDef, _register

PROMPT = """\
## 纯查询场景提示
仅当用户**只是问**价格 / 余额 / 能否用签到抵扣时：
- 需要针对具体字符数做预估时，调用 estimate_cost(service_type, model?, char_count?)。
- 只想对比总价时，直接引用 base 里的【可用工具及定价】回答，不要再调用 estimate_cost。
- 签到积分仅 lyrics 可用；其余服务扣充值积分。
- 回答后**不要主动启动音频生成**，等用户明确表态。

## 常见对照
- 1 积分 = 0.01 元
- Speech-2.8-HD 490 积分/万字符；Speech-2.8-Turbo 280 积分/万字符（约便宜 40%）
- 音乐生成 / 翻唱：140 积分/首，按次计费（target_duration 不影响价格）
- 声音克隆 / AI 声音设计：1386 积分/次
"""

_register(SkillDef(
    name="billing",
    description="计费预估：积分、价格、余额查询",
    keywords=[
        "价格", "费用", "积分", "花费", "多少钱", "余额",
        "计费", "cost", "credit", "便宜", "贵",
    ],
    priority=30,
    prompt_template=PROMPT,
    related_tools=["estimate_cost"],
))
