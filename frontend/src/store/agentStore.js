import { create } from 'zustand'

function normalizeTimelineItem(item) {
  if (item.type === 'message') {
    return {
      id: item.id,
      role: item.role,
      content: item.content,
      created_at: item.created_at,
    }
  }

  if (item.type === 'tool_call') {
    const done = !['pending', 'executing'].includes(item.status)
    return {
      id: item.id,
      role: done ? 'tool_result' : 'tool_call',
      tool_name: item.tool_name,
      params: item.params,
      result: item.result,
      status: done ? 'done' : item.status,
      error_message: item.error_message,
      models: item.models || [],
      created_at: item.created_at,
    }
  }

  return item
}

function upsertMessage(messages, nextMessage) {
  const index = messages.findIndex((message) => message.id === nextMessage.id)
  if (index === -1) {
    return [...messages, nextMessage]
  }
  return messages.map((message) => (message.id === nextMessage.id ? { ...message, ...nextMessage } : message))
}

function toolCallPath(toolCallId, action) {
  return `/api/agent/tool-calls/${encodeURIComponent(toolCallId)}/${action}`
}

const useAgentStore = create((set, get) => ({
  sessions: [],
  currentSessionId: null,
  sessionState: null,
  messages: [],
  streaming: false,
  streamingPhase: null,
  matchedSkills: [],
  error: null,

  loadSessions: async (api) => {
    try {
      const { data } = await api.get('/agent/sessions')
      set({ sessions: data })
    } catch (error) {
      set({ error: error.message || '加载会话失败' })
    }
  },

  createSession: async (api, title) => {
    const { data } = await api.post('/agent/sessions', { title })
    set((state) => ({
      sessions: [data, ...state.sessions],
      currentSessionId: data.id,
      messages: [],
      sessionState: null,
      error: null,
    }))
    return data.id
  },

  refreshSession: async (api, sessionId = null) => {
    const targetSessionId = sessionId || get().currentSessionId
    if (!targetSessionId) return
    try {
      const [timelineRes, stateRes] = await Promise.all([
        api.get(`/agent/sessions/${targetSessionId}/timeline`),
        api.get(`/agent/sessions/${targetSessionId}/state`),
      ])
      set({
        currentSessionId: targetSessionId,
        messages: timelineRes.data.map(normalizeTimelineItem),
        sessionState: stateRes.data,
        error: null,
      })
    } catch (error) {
      set({ error: error.message || '刷新会话失败' })
    }
  },

  selectSession: async (api, sessionId) => {
    set({ currentSessionId: sessionId, messages: [], sessionState: null, error: null })
    await get().refreshSession(api, sessionId)
  },

  deleteSession: async (api, sessionId) => {
    try {
      await api.delete(`/agent/sessions/${sessionId}`)
      set((state) => ({
        sessions: state.sessions.filter((session) => session.id !== sessionId),
        currentSessionId: state.currentSessionId === sessionId ? null : state.currentSessionId,
        messages: state.currentSessionId === sessionId ? [] : state.messages,
        sessionState: state.currentSessionId === sessionId ? null : state.sessionState,
      }))
    } catch (error) {
      set({ error: error.message || '删除会话失败' })
    }
  },

  clearRoleVoiceMemory: async (api, roleKey) => {
    if (!roleKey) return
    try {
      await api.delete(`/agent/voice-memory/${encodeURIComponent(roleKey)}`)
      await get().refreshSession(api)
    } catch (error) {
      set({ error: error.message || '清除角色记忆失败' })
    }
  },

  clearAllVoiceMemory: async (api) => {
    try {
      await api.delete('/agent/voice-memory')
      await get().refreshSession(api)
    } catch (error) {
      set({ error: error.message || '清除全部记忆失败' })
    }
  },

  uploadAttachments: async (api, files) => {
    let sessionId = get().currentSessionId
    if (!sessionId) {
      sessionId = await get().createSession(api)
    }

    const uploaded = []
    for (const file of files) {
      const form = new FormData()
      form.append('session_id', sessionId)
      form.append('file', file)
      const { data } = await api.post('/agent/uploads', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      uploaded.push(data)
    }
    return { sessionId, uploaded }
  },

  sendMessage: async (message, attachmentIds = []) => {
    const { currentSessionId } = get()
    if (!currentSessionId || get().streaming) return

    const userMessage = { id: `temp-${Date.now()}`, role: 'user', content: message }
    set((state) => ({
      messages: [...state.messages, userMessage],
      streaming: true,
      streamingPhase: 'thinking',
      matchedSkills: [],
      error: null,
    }))

    await get()._streamSSE('/api/agent/chat', {
      session_id: currentSessionId,
      message,
      attachments: attachmentIds,
    })
  },

  confirmTool: async (toolCallId, selectedModel, paramOverrides) => {
    const { currentSessionId } = get()
    if (!currentSessionId) return

    set((state) => ({
      messages: state.messages.map((message) =>
        message.id === toolCallId ? { ...message, status: 'executing' } : message
      ),
      streaming: true,
      streamingPhase: 'calling',
      error: null,
    }))

    await get()._streamSSE(toolCallPath(toolCallId, 'confirm'), {
      session_id: currentSessionId,
      selected_model: selectedModel,
      client_request_id: `${Date.now()}-${toolCallId}`,
      param_overrides: paramOverrides || null,
    })
  },

  cancelTool: async (api, toolCallId) => {
    const { currentSessionId } = get()
    if (!currentSessionId) return
    try {
      const { data } = await api.post(toolCallPath(toolCallId, 'cancel').slice('/api'.length), {
        session_id: currentSessionId,
      })
      set((state) => ({
        sessionState: data.state,
        messages: upsertMessage(
          state.messages,
          normalizeTimelineItem({
            id: data.tool_call.id,
            type: 'tool_call',
            tool_name: data.tool_call.tool_name,
            params: data.tool_call.tool_params,
            status: data.tool_call.status,
            result: { cancelled: true },
            error_message: null,
            models: data.tool_call.models || [],
            created_at: new Date().toISOString(),
          }),
        ),
      }))
    } catch (error) {
      set({ error: error.message || '取消工具失败' })
    }
  },

  _streamSSE: async (url, body) => {
    const token = localStorage.getItem('access_token')
    let assistantContent = ''
    let assistantMsgId = null

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const errText = await response.text()
        set({
          streaming: false,
          streamingPhase: null,
          error: errText || 'Request failed',
        })
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        let eventType = 'message'

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
            continue
          }
          if (!line.startsWith('data: ')) continue

          let data
          try {
            data = JSON.parse(line.slice(6))
          } catch {
            continue
          }

          switch (eventType) {
            case 'skills':
              set({ matchedSkills: data.skills || [] })
              break

            case 'state':
              set({ sessionState: data })
              break

            case 'assistant_delta':
              set({ streamingPhase: 'thinking' })
              assistantContent += data.content || ''
              if (!assistantMsgId) {
                assistantMsgId = `assistant-${Date.now()}`
                set((state) => ({
                  messages: [...state.messages, { id: assistantMsgId, role: 'assistant', content: assistantContent }],
                }))
              } else {
                set((state) => ({
                  messages: state.messages.map((message) =>
                    message.id === assistantMsgId ? { ...message, content: assistantContent } : message
                  ),
                }))
              }
              break

            case 'tool_call_created': {
              assistantContent = ''
              assistantMsgId = null
              const nextMessage = normalizeTimelineItem({
                id: data.id,
                type: 'tool_call',
                tool_name: data.tool_name,
                params: data.tool_params,
                status: data.status,
                result: data.result_payload,
                error_message: data.error_message,
                models: data.models || [],
                created_at: new Date().toISOString(),
              })
              set((state) => ({
                streamingPhase: null,
                messages: upsertMessage(state.messages, nextMessage),
              }))
              break
            }

            case 'tool_call_updated': {
              const nextMessage = normalizeTimelineItem({
                id: data.id,
                type: 'tool_call',
                tool_name: data.tool_name,
                params: data.tool_params,
                status: data.status,
                result: data.result_payload,
                error_message: data.error_message,
                models: data.models || [],
                created_at: new Date().toISOString(),
              })
              set((state) => ({
                streamingPhase: data.status === 'executing' ? 'calling' : state.streamingPhase,
                messages: upsertMessage(state.messages, nextMessage),
              }))
              break
            }

            case 'tool_result':
              assistantContent = ''
              assistantMsgId = null
              set((state) => ({
                streamingPhase: 'thinking',
                messages: upsertMessage(state.messages, {
                  id: data.tool_call_id,
                  role: 'tool_result',
                  tool_name: data.name,
                  result: data.result,
                  credits_cost: data.credits_cost,
                  status: 'done',
                }),
              }))
              break

            case 'balance_updated':
            case 'balance':
              window.dispatchEvent(new CustomEvent('agent:balance', { detail: data }))
              break

            case 'warning':
              set((state) => ({
                messages: [...state.messages, { id: `warning-${Date.now()}`, role: 'assistant', content: data.message }],
              }))
              break

            case 'error':
              set({ error: data.message })
              break

            default:
              break
          }

          eventType = 'message'
        }
      }
    } catch (error) {
      set({ error: error.message || '网络连接失败' })
    } finally {
      set({
        streaming: false,
        streamingPhase: null,
        matchedSkills: [],
      })
    }
  },
}))

export default useAgentStore
