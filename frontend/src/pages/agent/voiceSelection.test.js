import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyRoleVoiceSelections,
  buildInitialRoleSelections,
  buildVoiceSelectionOverrides,
} from './voiceSelection.js'

test('buildInitialRoleSelections uses recommended voice ids', () => {
  const voiceSelection = {
    roles: [
      { role: '旁白', selected_voice_id: 'announcer', candidates: [] },
      { role: '姚老', selected_voice_id: 'elder', candidates: [] },
    ],
  }

  assert.deepEqual(buildInitialRoleSelections(voiceSelection), {
    '旁白': 'announcer',
    '姚老': 'elder',
  })
})

test('applyRoleVoiceSelections updates matching segments', () => {
  const segments = [
    { role: '旁白', voice_id: 'old', text: 'a' },
    { role: '姚老', voice_id: 'old-elder', text: 'b' },
    { role: '姚老', voice_id: 'old-elder', text: 'c' },
  ]

  const nextSegments = applyRoleVoiceSelections(segments, {
    '旁白': 'announcer',
    '姚老': 'kind-elder',
  })

  assert.equal(nextSegments[0].voice_id, 'announcer')
  assert.equal(nextSegments[1].voice_id, 'kind-elder')
  assert.equal(nextSegments[2].voice_id, 'kind-elder')
})

test('buildVoiceSelectionOverrides updates segments and selected roles', () => {
  const params = {
    segments: [
      { role: '旁白', voice_id: 'old', text: 'a' },
      { role: '姚老', voice_id: 'old-elder', text: 'b' },
    ],
    voice_selection: {
      roles: [
        { role: '旁白', selected_voice_id: 'old' },
        { role: '姚老', selected_voice_id: 'old-elder' },
      ],
    },
  }

  const overrides = buildVoiceSelectionOverrides(params, {
    '旁白': 'announcer',
    '姚老': 'kind-elder',
  })

  assert.equal(overrides.segments[0].voice_id, 'announcer')
  assert.equal(overrides.segments[1].voice_id, 'kind-elder')
  assert.equal(overrides.voice_selection.roles[0].selected_voice_id, 'announcer')
  assert.equal(overrides.voice_selection.roles[1].selected_voice_id, 'kind-elder')
})
