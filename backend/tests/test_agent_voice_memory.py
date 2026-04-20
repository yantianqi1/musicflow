"""Tests for agent_voice_memory service (session-agnostic, user-level)."""

import asyncio
import unittest
from unittest import IsolatedAsyncioTestCase

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.database import Base
from backend.services.agent_voice_memory import (
    apply_memory_to_selection,
    clear_role_memory,
    clear_user_memory,
    list_user_memory,
    load_memory_map,
    normalize_role_key,
    save_memory_from_tool_params,
)


SAMPLE_VOICES = [
    {"voice_id": "male-qn-qingse", "voice_name": "青涩青年", "voice_type": "system"},
    {"voice_id": "male-qn-jingying", "voice_name": "精英青年", "voice_type": "system"},
    {"voice_id": "Chinese (Mandarin)_Radio_Host", "voice_name": "电台主播", "voice_type": "system"},
    {"voice_id": "audiobook_male_1", "voice_name": "有声书男声", "voice_type": "system"},
]


class NormalizeRoleKeyTests(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(normalize_role_key(""))
        self.assertIsNone(normalize_role_key(None))
        self.assertIsNone(normalize_role_key("   "))

    def test_strips_whitespace(self):
        self.assertEqual(normalize_role_key("陈迹"), "陈迹")
        self.assertEqual(normalize_role_key("  陈迹  "), "陈迹")
        self.assertEqual(normalize_role_key("陈 迹"), "陈迹")

    def test_lowercases_latin(self):
        self.assertEqual(normalize_role_key("Alice"), "alice")
        self.assertEqual(normalize_role_key("ALICE"), "alice")

    def test_narrator_aliases_collapse(self):
        self.assertEqual(normalize_role_key("旁白"), "旁白")
        self.assertEqual(normalize_role_key("叙述者"), "旁白")
        self.assertEqual(normalize_role_key("旁白/叙述"), "旁白")
        self.assertEqual(normalize_role_key("Narrator"), "旁白")
        self.assertEqual(normalize_role_key("narrator"), "旁白")

    def test_nfkc_normalizes_full_width(self):
        # Full-width digits/letters collapse; CJK unchanged.
        self.assertEqual(normalize_role_key("Ａlice"), "alice")


class VoiceMemoryDBTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.user_id = "test-user"

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def _session(self):
        return self.session_factory()

    async def test_save_inserts_then_updates_with_usage_count(self):
        async with self.session_factory() as db:
            tool_params = {
                "segments": [
                    {"role": "陈迹", "voice_id": "male-qn-qingse", "text": "你好"},
                    {"role": "旁白", "voice_id": "audiobook_male_1", "text": "月光下"},
                ]
            }
            await save_memory_from_tool_params(db, self.user_id, tool_params, session_id="sess-1")
            await db.commit()

            memory = await load_memory_map(db, self.user_id)
            self.assertEqual(memory["陈迹"]["voice_id"], "male-qn-qingse")
            self.assertEqual(memory["旁白"]["voice_id"], "audiobook_male_1")

            # Second call with a different voice for 陈迹
            tool_params_2 = {
                "segments": [
                    {"role": "陈迹", "voice_id": "male-qn-jingying", "text": "再见"},
                ]
            }
            await save_memory_from_tool_params(db, self.user_id, tool_params_2, session_id="sess-2")
            await db.commit()

            memory = await load_memory_map(db, self.user_id)
            self.assertEqual(memory["陈迹"]["voice_id"], "male-qn-jingying")

            items = await list_user_memory(db, self.user_id)
            chenji = next(item for item in items if item["role_key"] == "陈迹")
            self.assertEqual(chenji["usage_count"], 2)
            self.assertEqual(chenji["last_session_id"], "sess-2")

    async def test_save_skips_empty_role_or_voice(self):
        async with self.session_factory() as db:
            tool_params = {
                "segments": [
                    {"role": "", "voice_id": "male-qn-qingse", "text": "x"},
                    {"role": "陈迹", "voice_id": "", "text": "y"},
                    {"role": "   ", "voice_id": "male-qn-qingse", "text": "z"},
                ]
            }
            saved = await save_memory_from_tool_params(db, self.user_id, tool_params)
            await db.commit()
            self.assertEqual(saved, [])
            memory = await load_memory_map(db, self.user_id)
            self.assertEqual(memory, {})

    async def test_save_dedupes_by_normalized_key(self):
        async with self.session_factory() as db:
            tool_params = {
                "segments": [
                    {"role": "旁白", "voice_id": "audiobook_male_1", "text": "a"},
                    {"role": "旁白/叙述", "voice_id": "male-qn-qingse", "text": "b"},
                ]
            }
            await save_memory_from_tool_params(db, self.user_id, tool_params)
            await db.commit()
            memory = await load_memory_map(db, self.user_id)
            # Both collapse to "旁白" — the latest non-empty voice_id wins so the
            # user's final override in the confirmation card is what we persist.
            self.assertEqual(list(memory.keys()), ["旁白"])
            self.assertEqual(memory["旁白"]["voice_id"], "male-qn-qingse")

    async def test_apply_memory_overrides_and_flags(self):
        async with self.session_factory() as db:
            await save_memory_from_tool_params(
                db, self.user_id,
                {"segments": [{"role": "陈迹", "voice_id": "male-qn-jingying", "text": "x"}]},
            )
            await db.commit()

            voice_selection = {
                "roles": [
                    {
                        "role": "陈迹",
                        "selected_voice_id": "male-qn-qingse",
                        "candidates": [
                            {"voice_id": "male-qn-qingse", "voice_name": "青涩", "score": 80},
                            {"voice_id": "male-qn-jingying", "voice_name": "精英", "score": 70},
                        ],
                    }
                ]
            }
            updated, hits = await apply_memory_to_selection(db, self.user_id, voice_selection, SAMPLE_VOICES)
            self.assertEqual(hits, {"陈迹": "male-qn-jingying"})
            role = updated["roles"][0]
            self.assertEqual(role["selected_voice_id"], "male-qn-jingying")
            self.assertTrue(role["from_memory"])
            # Memorized voice must be first in candidates.
            self.assertEqual(role["candidates"][0]["voice_id"], "male-qn-jingying")

    async def test_apply_memory_falls_back_if_voice_missing_from_catalog(self):
        async with self.session_factory() as db:
            await save_memory_from_tool_params(
                db, self.user_id,
                {"segments": [{"role": "陈迹", "voice_id": "deleted-custom-voice", "text": "x"}]},
            )
            await db.commit()

            voice_selection = {
                "roles": [
                    {
                        "role": "陈迹",
                        "selected_voice_id": "male-qn-qingse",
                        "candidates": [{"voice_id": "male-qn-qingse", "voice_name": "青涩", "score": 80}],
                    }
                ]
            }
            updated, hits = await apply_memory_to_selection(db, self.user_id, voice_selection, SAMPLE_VOICES)
            self.assertEqual(hits, {})
            role = updated["roles"][0]
            self.assertEqual(role["selected_voice_id"], "male-qn-qingse")
            self.assertFalse(role.get("from_memory"))

    async def test_apply_memory_prepends_fallback_when_not_in_candidates(self):
        async with self.session_factory() as db:
            await save_memory_from_tool_params(
                db, self.user_id,
                {"segments": [{"role": "陈迹", "voice_id": "Chinese (Mandarin)_Radio_Host", "text": "x"}]},
            )
            await db.commit()

            voice_selection = {
                "roles": [
                    {
                        "role": "陈迹",
                        "selected_voice_id": "male-qn-qingse",
                        "candidates": [{"voice_id": "male-qn-qingse", "voice_name": "青涩", "score": 80}],
                    }
                ]
            }
            updated, _ = await apply_memory_to_selection(db, self.user_id, voice_selection, SAMPLE_VOICES)
            candidate_ids = [c["voice_id"] for c in updated["roles"][0]["candidates"]]
            self.assertEqual(candidate_ids[0], "Chinese (Mandarin)_Radio_Host")

    async def test_apply_memory_no_hits_when_empty(self):
        async with self.session_factory() as db:
            voice_selection = {
                "roles": [
                    {
                        "role": "陈迹",
                        "selected_voice_id": "male-qn-qingse",
                        "candidates": [{"voice_id": "male-qn-qingse", "score": 80}],
                    }
                ]
            }
            updated, hits = await apply_memory_to_selection(db, self.user_id, voice_selection, SAMPLE_VOICES)
            self.assertEqual(hits, {})
            self.assertFalse(updated["roles"][0].get("from_memory"))

    async def test_clear_role_and_clear_all(self):
        async with self.session_factory() as db:
            await save_memory_from_tool_params(
                db, self.user_id,
                {"segments": [
                    {"role": "陈迹", "voice_id": "male-qn-qingse", "text": "a"},
                    {"role": "旁白", "voice_id": "audiobook_male_1", "text": "b"},
                ]},
            )
            await db.commit()

            removed = await clear_role_memory(db, self.user_id, "陈迹")
            await db.commit()
            self.assertEqual(removed, 1)
            memory = await load_memory_map(db, self.user_id)
            self.assertNotIn("陈迹", memory)
            self.assertIn("旁白", memory)

            removed_all = await clear_user_memory(db, self.user_id)
            await db.commit()
            self.assertEqual(removed_all, 1)
            memory = await load_memory_map(db, self.user_id)
            self.assertEqual(memory, {})

    async def test_clear_role_accepts_unnormalized_key(self):
        async with self.session_factory() as db:
            await save_memory_from_tool_params(
                db, self.user_id,
                {"segments": [{"role": "旁白", "voice_id": "audiobook_male_1", "text": "a"}]},
            )
            await db.commit()
            # Caller passes "旁白/叙述" — should still clear the "旁白" row.
            removed = await clear_role_memory(db, self.user_id, "旁白/叙述")
            await db.commit()
            self.assertEqual(removed, 1)


if __name__ == "__main__":
    unittest.main()
