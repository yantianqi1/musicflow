import unittest

from backend.services.voice_casting import (
    build_voice_selection,
    enrich_batch_voice_over_params,
    format_voice_list_for_prompt,
)


class VoiceCastingTests(unittest.TestCase):
    def test_narrator_roles_prefer_narration_voices(self):
        voices = [
            {"voice_id": "Chinese (Mandarin)_Male_Announcer", "voice_name": "播报男声", "voice_type": "system"},
            {"voice_id": "Chinese (Mandarin)_Radio_Host", "voice_name": "电台男主播", "voice_type": "system"},
            {"voice_id": "male-qn-qingse", "voice_name": "青涩青年音色", "voice_type": "system"},
        ]
        segments = [
            {"role": "旁白", "voice_id": "male-qn-qingse", "text": "夜色渐深，风从巷口吹过。"},
        ]

        selection = build_voice_selection(segments, voices)
        narrator = selection["roles"][0]

        self.assertEqual("旁白/叙述", narrator["role_summary"])
        self.assertEqual(3, len(narrator["candidates"]))
        self.assertIn(narrator["selected_voice_id"], {"Chinese (Mandarin)_Male_Announcer", "Chinese (Mandarin)_Radio_Host"})

    def test_elder_roles_prefer_elder_voices(self):
        voices = [
            {"voice_id": "Chinese (Mandarin)_Kind-hearted_Elder", "voice_name": "花甲奶奶", "voice_type": "system"},
            {"voice_id": "Chinese (Mandarin)_Humorous_Elder", "voice_name": "搞笑大爷", "voice_type": "system"},
            {"voice_id": "male-qn-jingying", "voice_name": "精英青年音色", "voice_type": "system"},
            {"voice_id": "male-qn-qingse", "voice_name": "青涩青年音色", "voice_type": "system"},
        ]
        segments = [
            {"role": "姚老", "voice_id": "male-qn-jingying", "text": "后悔吗？"},
            {"role": "姚老", "voice_id": "male-qn-jingying", "text": "年纪大了以后，酒喝起来有点苦。"},
        ]

        selection = build_voice_selection(segments, voices)
        elder = selection["roles"][0]

        self.assertEqual("老年角色", elder["role_summary"])
        self.assertEqual(3, len(elder["candidates"]))
        self.assertEqual("Chinese (Mandarin)_Humorous_Elder", elder["selected_voice_id"])

    def test_current_voice_is_preserved_as_fallback_candidate(self):
        voices = [
            {"voice_id": "Chinese (Mandarin)_Male_Announcer", "voice_name": "播报男声", "voice_type": "system"},
            {"voice_id": "male-qn-qingse", "voice_name": "青涩青年音色", "voice_type": "system"},
        ]
        segments = [
            {"role": "旁白", "voice_id": "audiobook_male_1", "text": "他推门而入，屋里亮着暖黄的灯。"},
        ]

        selection = build_voice_selection(segments, voices)
        candidate_ids = [item["voice_id"] for item in selection["roles"][0]["candidates"]]

        self.assertIn("audiobook_male_1", candidate_ids)

    def test_chinese_roles_prefer_chinese_youth_voices(self):
        voices = [
            {"voice_id": "Arabic_CalmWoman", "voice_name": "Arabic Calm Woman", "voice_type": "system"},
            {"voice_id": "Cantonese_KindWoman", "voice_name": "温柔女声", "voice_type": "system"},
            {"voice_id": "Chinese (Mandarin)_Gentle_Youth", "voice_name": "温润青年", "voice_type": "system"},
            {"voice_id": "male-qn-qingse", "voice_name": "青涩青年音色", "voice_type": "system"},
        ]
        segments = [
            {"role": "陈迹", "voice_id": "male-qn-qingse", "text": "乌鸦叔，好久不见。"},
        ]

        selection = build_voice_selection(segments, voices)
        candidate_ids = [item["voice_id"] for item in selection["roles"][0]["candidates"]]

        self.assertEqual("male-qn-qingse", selection["roles"][0]["selected_voice_id"])
        self.assertIn("Chinese (Mandarin)_Gentle_Youth", candidate_ids)
        self.assertNotIn("Arabic_CalmWoman", candidate_ids[:2])

    def test_prompt_uses_voice_names_and_custom_section(self):
        voices = [
            {"voice_id": "male-qn-qingse", "voice_name": "青涩青年音色", "voice_type": "system"},
            {"voice_id": "voice_demo", "voice_name": "店主叔叔", "voice_type": "cloned"},
        ]

        prompt = format_voice_list_for_prompt(voices)

        self.assertIn("### 系统音色", prompt)
        self.assertIn("male-qn-qingse(青涩青年音色)", prompt)
        self.assertIn("### 用户自定义音色（优先考虑使用）", prompt)
        self.assertIn("voice_demo(店主叔叔)", prompt)

    def test_enrich_batch_params_adds_voice_selection_and_updates_segments(self):
        voices = [
            {"voice_id": "Chinese (Mandarin)_Male_Announcer", "voice_name": "播报男声", "voice_type": "system"},
            {"voice_id": "Chinese (Mandarin)_Humorous_Elder", "voice_name": "搞笑大爷", "voice_type": "system"},
            {"voice_id": "male-qn-qingse", "voice_name": "青涩青年音色", "voice_type": "system"},
        ]
        tool_params = {
            "segments": [
                {"role": "旁白", "voice_id": "male-qn-qingse", "text": "夜色渐深。"},
                {"role": "姚老", "voice_id": "male-qn-qingse", "text": "后悔吗？"},
            ],
            "model": "speech-2.8-hd",
        }

        enriched = enrich_batch_voice_over_params(tool_params, voices)

        self.assertIn("voice_selection", enriched)
        self.assertEqual("Chinese (Mandarin)_Male_Announcer", enriched["segments"][0]["voice_id"])
        self.assertEqual("Chinese (Mandarin)_Humorous_Elder", enriched["segments"][1]["voice_id"])


if __name__ == "__main__":
    unittest.main()
