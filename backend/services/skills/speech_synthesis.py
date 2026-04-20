"""Speech synthesis skill — single-voice TTS."""

from backend.services.agent_skills import SkillDef, _register

PROMPT = """\
## 语音合成指南

### 模式选择
- **短文本（≤1万字符）**：使用 text_to_speech（同步，实时返回音频）
- **长文本（>1万字符）**：使用 long_text_to_speech（异步，返回任务ID，需用 query_task_status 查询进度）

### 模型选择建议（UI 最终决定，你只给倾向）
- **speech-2.8-hd** (490 积分/万字符)：长篇朗读、多角色小说、需要细腻情感层次 → 推荐。
- **speech-2.8-turbo** (280 积分/万字符)：短提醒、通知音、预算敏感 → 推荐（比 HD 便宜约 40%）。
- 默认 model 填 `speech-2.8-hd`；用户在确认卡片里自行切换，**不要用文字问"HD 还是 Turbo"**。

### 音色选择
- 不确定音色时，先调用 list_voices 查询可用音色
- 用户有自定义音色时优先使用
- 不要编造音色ID

### 参数说明
- speed（语速）: 0.5~2.0，默认 1.0
- pitch（音调）: -12~12，默认 0
- vol（音量）: 0.1~10.0，默认 1.0
- emotion: happy/sad/angry/fearful/disgusted/surprised/fluent/calm，不设则自动判断
- language_boost: 语言增强，支持 Chinese/English/Japanese 等，默认 auto
"""

_register(SkillDef(
    name="speech_synthesis",
    description="语音合成：文字转语音",
    keywords=[
        "语音", "朗读", "播报", "TTS", "合成", "读出来", "念",
        "播放文字", "文字转语音", "念出来", "读给我听",
    ],
    priority=50,
    prompt_template=PROMPT,
    related_tools=["text_to_speech", "long_text_to_speech", "list_voices"],
))
