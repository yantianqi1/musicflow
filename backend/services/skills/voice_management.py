"""Voice management skill — clone, design, list, delete voices."""

from backend.services.agent_skills import SkillDef, _register

PROMPT = """\
## 声音管理

### 声音克隆流程
1. 用户需先上传参考音频（调用 upload_file，purpose=voice_clone）
2. 音频要求：mp3/m4a/wav，10秒~5分钟，<20MB
3. 获得 file_id 后，调用 clone_voice 进行克隆
4. 克隆成功后可在语音合成中使用该音色

### AI 声音设计
- 用自然语言描述想要的声音特征，如"成熟稳重的男性声音，低沉有磁性"
- 调用 design_voice，系统会生成对应音色
- 生成后可在语音合成中使用

### 声音列表查询
- 调用 list_voices 查看所有可用音色
- voice_type 可选: all/system/voice_cloning/voice_generation

### 删除声音
- 调用 delete_voice 删除自定义音色
- 系统预置音色不可删除
"""

_register(SkillDef(
    name="voice_management",
    description="声音管理：克隆、设计、查询、删除",
    keywords=[
        "克隆", "音色", "设计声音", "自定义声音", "上传音频",
        "clone", "voice", "删除声音", "我的声音", "声音列表",
    ],
    priority=40,
    prompt_template=PROMPT,
    related_tools=["clone_voice", "design_voice", "list_voices", "delete_voice", "upload_file"],
))
