"""Music creation skill — lyrics, music generation, covers."""

from backend.services.agent_skills import SkillDef, _register

PROMPT = """\
## 价格要点
- generate_music / generate_cover: 140 积分/首，**按次计费**；target_duration 只影响歌曲结构，不影响价格。
- generate_lyrics: 7 积分/次，**可用签到积分**。

## 时长控制（重要）
MiniMax 没有直接的时长参数，音乐时长由歌词长度/结构决定：
- short (20-40秒): 仅1段(Verse或Chorus)，4-6行
- medium (1-2分钟): Verse+Chorus，8-14行
- standard (2-3分钟): 完整结构 Verse+Chorus+Verse+Chorus+Bridge+Outro，16-24行
- long (3-4分钟): 丰富结构 Intro+Verse+PreChorus+Chorus+Verse+Chorus+Bridge+Chorus+Outro，24-36行

当用户提到时长需求时（如"30秒BGM"、"一首完整的歌"），你必须设置 target_duration 参数。
对纯器乐(BGM)，系统会自动在prompt中附加时长提示。
如果用户没提时长，默认使用 standard。
"""

_register(SkillDef(
    name="music_creation",
    description="音乐创作：歌词生成、音乐生成、翻唱",
    keywords=[
        "音乐", "歌曲", "歌词", "旋律", "编曲", "BGM", "伴奏",
        "翻唱", "cover", "混音", "器乐", "纯音乐", "作曲", "谱曲",
        "唱", "歌", "曲", "rap", "说唱", "摇滚", "流行",
    ],
    priority=50,
    prompt_template=PROMPT,
    related_tools=["generate_lyrics", "generate_music", "generate_cover"],
))
