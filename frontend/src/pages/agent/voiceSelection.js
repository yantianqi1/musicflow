export function buildInitialRoleSelections(voiceSelection) {
  const roles = voiceSelection?.roles || []
  return roles.reduce((result, role) => {
    if (role?.role && role?.selected_voice_id) {
      result[role.role] = role.selected_voice_id
    }
    return result
  }, {})
}

export function isRoleFromMemory(role) {
  return !!role?.from_memory
}

export function applyRoleVoiceSelections(segments, selections) {
  return (segments || []).map((segment) => {
    const nextVoiceId = selections?.[segment.role]
    if (!nextVoiceId) {
      return { ...segment }
    }
    return { ...segment, voice_id: nextVoiceId }
  })
}

export function buildVoiceSelectionOverrides(params, selections) {
  const nextSegments = applyRoleVoiceSelections(params?.segments || [], selections)
  const nextVoiceSelection = {
    ...(params?.voice_selection || {}),
    roles: (params?.voice_selection?.roles || []).map((role) => ({
      ...role,
      selected_voice_id: selections?.[role.role] || role.selected_voice_id,
    })),
  }

  return {
    segments: nextSegments,
    voice_selection: nextVoiceSelection,
  }
}
