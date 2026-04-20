import { useState, useEffect, useLayoutEffect, useRef, useMemo } from 'react'
import { Bot, Plus, Send, Trash2, Coins, ChevronDown, Loader2, AlertCircle, Check, Music, Mic, Sparkles, AudioWaveform, MessageSquare, Wrench, ThumbsUp, PenLine, RefreshCw, PenTool, Volume2, BookOpen, Users, Fingerprint, Wand2, List, Calculator, Search, Paperclip, X, FileText, Image, Copy, ChevronUp, Bookmark, Menu } from 'lucide-react'
import api from '../../api/client'
import useAgentStore from '../../store/agentStore'
import useAuthStore from '../../store/authStore'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import AudioPlayer from '../../components/AudioPlayer'
import { buildInitialRoleSelections, buildVoiceSelectionOverrides } from './voiceSelection'

const TOOL_META = {
  generate_lyrics: { label: '歌词生成', Icon: PenTool, gradient: 'from-indigo-500 to-blue-500' },
  generate_music: { label: '音乐生成', Icon: Music, gradient: 'from-violet-500 to-purple-500' },
  generate_cover: { label: '翻唱生成', Icon: Mic, gradient: 'from-pink-500 to-rose-500' },
  text_to_speech: { label: '语音合成', Icon: Volume2, gradient: 'from-emerald-500 to-teal-500' },
  long_text_to_speech: { label: '长文本语音', Icon: BookOpen, gradient: 'from-cyan-500 to-blue-500' },
  batch_voice_over: { label: '多角色配音', Icon: Users, gradient: 'from-amber-500 to-orange-500' },
  clone_voice: { label: '声音克隆', Icon: Fingerprint, gradient: 'from-purple-500 to-indigo-500' },
  design_voice: { label: '声音设计', Icon: Wand2, gradient: 'from-fuchsia-500 to-pink-500' },
  list_voices: { label: '查询声音', Icon: List, gradient: 'from-slate-500 to-gray-500' },
  estimate_cost: { label: '费用预估', Icon: Calculator, gradient: 'from-green-500 to-emerald-500' },
  query_task_status: { label: '任务查询', Icon: Search, gradient: 'from-sky-500 to-blue-500' },
}

// Tools whose results auto-collapse (informational/query tools)
const AUTO_COLLAPSE_TOOLS = new Set(['estimate_cost', 'list_voices', 'query_task_status'])

// Tools whose results are always shown prominently (not hidden in process group)
const RESULT_TOOLS = new Set([
  'batch_voice_over', 'generate_music', 'generate_cover',
  'text_to_speech', 'long_text_to_speech', 'generate_lyrics',
  'clone_voice', 'design_voice',
])

// Per-tool model recommendation text shown on the confirm card
const MODEL_RECOMMENDATION = {
  batch_voice_over: {
    'speech-2.8-hd': '长篇多角色推荐',
    'speech-2.8-turbo': '批量预算推荐',
  },
  long_text_to_speech: {
    'speech-2.8-hd': '高质量长篇',
    'speech-2.8-turbo': '预算优先',
  },
  text_to_speech: {
    'speech-2.8-turbo': '短句日常够用',
  },
}

const CHAT_INPUT_MAX_HEIGHT = 200

function resizeChatInput(el) {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, CHAT_INPUT_MAX_HEIGHT) + 'px'
}

function isResultMessage(msg) {
  if (msg.role !== 'tool_result') return false
  return RESULT_TOOLS.has(msg.tool_name)
}

function groupMessages(messages) {
  const groups = []
  let buf = []
  const flush = () => {
    if (buf.length > 0) {
      groups.push({ type: 'process', messages: [...buf], id: 'p-' + buf[0].id })
      buf = []
    }
  }
  for (const msg of messages) {
    if (msg.role === 'user') {
      flush()
      groups.push({ type: 'user', message: msg, id: msg.id })
    } else if (isResultMessage(msg)) {
      flush()
      groups.push({ type: 'result', message: msg, id: msg.id })
    } else {
      buf.push(msg)
    }
  }
  flush()
  return groups
}

// =========================================================================
// Main Workspace
// =========================================================================

export default function AgentWorkspace() {
  const {
    sessions, currentSessionId, sessionState, messages, streaming, streamingPhase, matchedSkills, error,
    loadSessions, createSession, selectSession, deleteSession, uploadAttachments, sendMessage, confirmTool, cancelTool,
  } = useAgentStore()
  const { user, updateCredits } = useAuthStore()
  const [input, setInput] = useState('')
  const [attachedFiles, setAttachedFiles] = useState([])
  const [sessionSheetOpen, setSessionSheetOpen] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)
  const groups = useMemo(() => groupMessages(messages), [messages])

  const currentSession = sessions.find((s) => s.id === currentSessionId)

  useLayoutEffect(() => {
    resizeChatInput(inputRef.current)
  }, [input])

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    setAttachedFiles(prev => [...prev, ...files].slice(0, 5))
    e.target.value = ''
  }

  const removeFile = (index) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== index))
  }

  useEffect(() => { loadSessions(api) }, [])

  useEffect(() => {
    const handler = (e) => { if (e.detail) updateCredits(e.detail.credits, e.detail.free_credits) }
    window.addEventListener('agent:balance', handler)
    return () => window.removeEventListener('agent:balance', handler)
  }, [updateCredits])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || streaming) return

    const pendingToolIds = messages
      .filter((m) => m.role === 'tool_call' && m.status === 'pending')
      .map((m) => m.id)
    for (const pid of pendingToolIds) {
      await cancelTool(api, pid)
    }

    let sessionId = currentSessionId
    let attachmentIds = []

    if (!sessionId && attachedFiles.length === 0) {
      sessionId = await createSession(api, text.slice(0, 50))
    }

    if (attachedFiles.length > 0) {
      const uploaded = await uploadAttachments(api, attachedFiles)
      sessionId = uploaded.sessionId
      attachmentIds = uploaded.uploaded.map((item) => item.id)
    }

    setInput('')
    setAttachedFiles([])

    if (!sessionId) return
    const delay = pendingToolIds.length > 0 || !currentSessionId ? 120 : 0
    if (delay > 0) {
      setTimeout(() => sendMessage(text, attachmentIds), delay)
    } else {
      sendMessage(text, attachmentIds)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  // Check if there's a pending tool_call that needs user action (not streaming)
  const hasPendingTool = !streaming && (
    sessionState?.status === 'awaiting_confirmation'
    || messages.some((m) => m.role === 'tool_call' && m.status === 'pending')
  )

  return (
    <div className="flex flex-col lg:flex-row animate-fade-in -mx-4 -mt-4 lg:-m-6 h-[calc(100dvh-136px-env(safe-area-inset-top)-env(safe-area-inset-bottom))] lg:h-[calc(100vh-3rem)]">
      {/* Mobile top bar: hamburger + session title + new-chat */}
      <div
        className="lg:hidden flex items-center justify-between gap-2 px-3 h-12 border-b border-black/5 flex-shrink-0"
        style={{ background: '#fff' }}
      >
        <button
          onClick={() => setSessionSheetOpen(true)}
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ color: 'var(--color-text-light)' }}
          aria-label="会话列表"
        >
          <Menu size={18} />
        </button>
        <div
          className="text-[13px] font-semibold truncate text-center flex-1 min-w-0"
          style={{ color: '#1e293b' }}
        >
          {currentSession?.title || 'Lyra · AI 音乐创作'}
        </div>
        <button
          onClick={() => createSession(api)}
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ color: 'var(--color-primary)' }}
          aria-label="新对话"
        >
          <Plus size={18} />
        </button>
      </div>

      {/* Desktop session sidebar */}
      <aside className="hidden lg:flex w-60 flex-shrink-0 flex-col border-r border-[rgba(0,0,0,0.06)]" style={{ background: 'var(--color-surface-light)' }}>
        <div className="p-3">
          <button onClick={() => createSession(api)} className="w-full flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl border border-[rgba(0,0,0,0.08)] bg-white hover:bg-[var(--color-surface)] text-sm font-medium text-text transition-all duration-150 hover:shadow-sm">
            <Plus size={16} /> 新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => selectSession(api, s.id)}
              className={`group flex items-center gap-2.5 px-3 py-2.5 rounded-xl cursor-pointer text-sm transition-all duration-150 ${
                currentSessionId === s.id
                  ? 'bg-white shadow-sm text-text font-medium'
                  : 'text-text-light hover:bg-white/60'
              }`}
            >
              <MessageSquare size={14} className="flex-shrink-0 opacity-50" />
              <span className="flex-1 truncate">{s.title || '新对话'}</span>
              <button
                onClick={(e) => { e.stopPropagation(); deleteSession(api, s.id) }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:text-danger transition-opacity"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Mobile session bottom sheet */}
      {sessionSheetOpen && (
        <div className="lg:hidden" role="dialog" aria-modal="true">
          <div className="mobile-sheet-backdrop" onClick={() => setSessionSheetOpen(false)} />
          <div className="mobile-sheet-panel" style={{ maxHeight: '75vh' }}>
            <div className="flex justify-center pt-2.5 pb-1">
              <div className="w-10 h-1 rounded-full bg-[rgba(0,0,0,0.15)]" />
            </div>
            <div className="flex items-center justify-between px-5 pt-2 pb-3">
              <h3 className="text-base font-semibold" style={{ color: '#1e293b' }}>会话</h3>
              <button
                onClick={() => { createSession(api); setSessionSheetOpen(false) }}
                className="neu-btn !text-xs !min-h-[36px] !py-2 !px-3 gap-1"
              >
                <Plus size={14} /> 新对话
              </button>
            </div>
            <div className="h-px mx-5 bg-[rgba(0,0,0,0.06)]" />
            <div className="px-3 py-3 space-y-1.5 overflow-y-auto" style={{ maxHeight: 'calc(75vh - 120px)' }}>
              {sessions.length === 0 && (
                <p className="text-sm text-text-muted text-center py-6">还没有对话</p>
              )}
              {sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => { selectSession(api, s.id); setSessionSheetOpen(false) }}
                  className={`flex items-center gap-2.5 p-3 rounded-[14px] cursor-pointer transition-all ${
                    currentSessionId === s.id
                      ? 'shadow-neu-inset text-primary font-semibold'
                      : 'shadow-neu-sm active:shadow-neu-inset'
                  }`}
                  style={{ background: 'var(--color-surface)', minHeight: '52px' }}
                >
                  <MessageSquare size={16} className="flex-shrink-0 opacity-60" />
                  <span className="flex-1 truncate text-sm">{s.title || '新对话'}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteSession(api, s.id) }}
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-text-muted hover:text-danger"
                    aria-label="删除会话"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-h-0" style={{ background: '#fff' }}>
        <div className="flex-1 overflow-y-auto px-4 pt-4 pb-3">
          <div className="chat-content-centered">
          {messages.length === 0 && !streaming && (
            <WelcomeScreen onSuggestion={(text) => { setInput(text); inputRef.current?.focus() }} />
          )}

          {groups.map((group, gi) => {
            if (group.type === 'user') {
              return <ChatBubble key={group.id} message={group.message} />
            }
            if (group.type === 'result') {
              return <ToolResultBubble key={group.id} message={group.message} />
            }
            // Process group: single message → show inline, multiple → collapsible
            if (group.messages.length === 1) {
              const msg = group.messages[0]
              if (msg.role === 'tool_call') {
                return (
                  <ToolConfirmCard
                    key={msg.id}
                    msg={msg}
                    userCredits={user?.credits ?? 0}
                    userFreeCredits={user?.free_credits ?? 0}
                    onConfirm={(model, extraParams) => confirmTool(msg.id, model, extraParams)}
                    onCancel={() => cancelTool(api, msg.id)}
                    disabled={streaming}
                  />
                )
              }
              return <ChatBubble key={msg.id} message={msg} />
            }
            return (
              <ProcessGroup
                key={group.id}
                messages={group.messages}
                isLast={gi === groups.length - 1}
              >
                {group.messages.map(msg => {
                  if (msg.role === 'tool_call') {
                    return (
                      <ToolConfirmCard
                        key={msg.id}
                        msg={msg}
                        userCredits={user?.credits ?? 0}
                        userFreeCredits={user?.free_credits ?? 0}
                        onConfirm={(model, extraParams) => confirmTool(msg.id, model, extraParams)}
                        onCancel={() => cancelTool(api, msg.id)}
                        disabled={streaming}
                      />
                    )
                  }
                  return <ChatBubble key={msg.id} message={msg} />
                })}
              </ProcessGroup>
            )
          })}

          {/* Streaming status */}
          {streaming && (
            <StreamingStatus phase={streamingPhase} skills={matchedSkills} />
          )}

          {error && (
            <div className="flex items-start gap-2 text-sm text-danger py-3 animate-fade-in">
              <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Quick reply buttons */}
          {!streaming && messages.length > 0 && (
            <QuickReplies
              messages={messages}
              onSend={(text) => {
                setInput('')
                if (currentSessionId) sendMessage(text)
              }}
              disabled={streaming || hasPendingTool}
            />
          )}

          <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="chat-input-area">
          <div className="chat-input-card">
            {/* Attached files preview */}
            {attachedFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 px-4 pt-3">
                {attachedFiles.map((file, i) => (
                  <div key={i} className="chat-file-chip">
                    {file.type?.startsWith('image/') ? <Image size={14} /> : <FileText size={14} />}
                    <span className="truncate max-w-[120px]">{file.name}</span>
                    <button onClick={() => removeFile(i)} className="chat-file-chip-remove">
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Input row */}
            <div className="flex items-end gap-2 p-3">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="audio/*,image/*,.txt,.srt,.lrc"
                className="hidden"
                onChange={handleFileSelect}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={streaming}
                className="chat-input-action-btn flex-shrink-0"
                title="上传文件"
              >
                <Paperclip size={18} />
              </button>

              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={hasPendingTool ? '直接发送可取消上方工具调用并重新描述...' : '描述你想做的音频任务，Shift+Enter 换行...'}
                rows={1}
                className="chat-input-textarea"
                disabled={streaming}
              />

              <button
                onClick={handleSend}
                disabled={!input.trim() || streaming}
                className={`chat-send-btn flex-shrink-0 ${input.trim() && !streaming ? 'chat-send-btn-active' : ''}`}
              >
                <Send size={18} />
              </button>
            </div>

            {/* Bottom bar: credits + hint */}
            <div className="flex items-center justify-between px-4 pb-2.5 text-xs text-text-muted">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1"><Coins size={12} /> {user?.credits ?? 0}</span>
                <span className="flex items-center gap-1" style={{ color: 'var(--color-success)' }}>签到 {user?.free_credits ?? 0}</span>
              </div>
              <span className="opacity-50">Enter 发送 · Shift+Enter 换行</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


// =========================================================================
// Streaming Status (thinking / calling tool)
// =========================================================================

function StreamingStatus({ phase, skills }) {
  const labels = {
    thinking: '思考中',
    calling: '工具执行中',
  }
  return (
    <div className="chat-msg-row animate-fade-in">
      <div className="chat-avatar chat-avatar-ai">
        <Sparkles size={14} />
      </div>
      <div className="chat-streaming-pill">
        <div className="chat-streaming-dot" />
        <span>{labels[phase] || '处理中'}</span>
        {phase === 'thinking' && skills && skills.length > 0 && (
          <span className="text-text-muted opacity-60 ml-1">· {skills.join('、')}</span>
        )}
      </div>
    </div>
  )
}


// =========================================================================
// Process Group — collapsible wrapper for AI working steps
// =========================================================================

function ProcessGroup({ messages, isLast, children }) {
  const hasPending = messages.some(m => m.role === 'tool_call' && m.status === 'pending')
  const hasExecuting = messages.some(m => m.role === 'tool_call' && m.status === 'executing')
  const [expanded, setExpanded] = useState(() => isLast || hasPending || hasExecuting)
  const prevIsLastRef = useRef(isLast)

  useEffect(() => {
    // Auto-collapse when a result appears after this group
    if (prevIsLastRef.current && !isLast) setExpanded(false)
    // Force expand for active interactions
    if (hasPending || hasExecuting) setExpanded(true)
    prevIsLastRef.current = isLast
  }, [isLast, hasPending, hasExecuting])

  const toolSteps = messages
    .filter(m => m.role === 'tool_call' || m.role === 'tool_result')
    .map(m => TOOL_META[m.tool_name]?.label)
    .filter(Boolean)
    .filter((v, i, a) => a.indexOf(v) === i)

  return (
    <div className="animate-fade-in py-1">
      <button
        onClick={() => setExpanded(e => !e)}
        className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs w-full text-left transition-all duration-150 hover:bg-[var(--color-surface-light)]"
      >
        <ChevronDown
          size={13}
          className={`text-text-muted transition-transform duration-200 flex-shrink-0 ${expanded ? '' : '-rotate-90'}`}
        />
        <Bot size={13} className="text-text-muted flex-shrink-0" />
        <span className="text-text-muted font-medium">AI 工作过程</span>
        {toolSteps.length > 0 && (
          <span className="text-text-muted opacity-60 truncate">· {toolSteps.join(' → ')}</span>
        )}
        <span className="ml-auto text-text-muted opacity-50 flex-shrink-0">{messages.length} 条</span>
      </button>

      {expanded && (
        <div className="mt-2 space-y-1 pl-5 ml-1.5 border-l-2 border-[var(--color-surface-dark)]">
          {children}
        </div>
      )}
    </div>
  )
}


// =========================================================================
// Quick Replies — clickable action buttons when assistant asks for confirmation
// =========================================================================

const QUICK_REPLY_RULES = [
  {
    // After cost estimation for voice-over / TTS, offer confirm or modify
    match: (msgs) => {
      const last = [...msgs].reverse()
      const lastAssistant = last.find(m => m.role === 'assistant')
      const hasEstimate = last.find(m => m.role === 'tool_result' && m.tool_name === 'estimate_cost')
      if (!lastAssistant || !hasEstimate) return false
      // Check the estimate came after or near the assistant message asking for confirmation
      const assistantIdx = msgs.indexOf(lastAssistant)
      const estimateIdx = msgs.indexOf(hasEstimate)
      return estimateIdx >= assistantIdx - 2 && /确认|开始|同意|满意/.test(lastAssistant.content || '')
    },
    replies: [
      { label: '确认，开始合成', icon: ThumbsUp, style: 'primary' },
      { label: '修改角色分配', icon: PenLine, style: 'default' },
      { label: '换个模型再估价', icon: RefreshCw, style: 'default' },
    ],
  },
  {
    // Generic confirmation: assistant asks yes/no style questions
    match: (msgs) => {
      const last = [...msgs].reverse().find(m => m.role === 'assistant')
      if (!last?.content) return false
      return /是否满意|是否确认|确认后|确认无误|可以开始|需要调整/.test(last.content)
        && !/已经为您|合成完成|生成完成/.test(last.content)
    },
    replies: [
      { label: '确认，继续', icon: ThumbsUp, style: 'primary' },
      { label: '需要调整', icon: PenLine, style: 'default' },
    ],
  },
  {
    // Auto-extract option lists from "例如：A、B、C 或 D" / "可选：..." / "A 还是 B？"
    match: (msgs) => {
      const last = [...msgs].reverse().find(m => m.role === 'assistant')
      if (!last?.content) return false
      if (/已经为您|已完成|合成完成|生成完成|执行成功/.test(last.content)) return false
      return extractInlineOptions(last.content).length >= 2
    },
    extract: (msgs) => {
      const last = [...msgs].reverse().find(m => m.role === 'assistant')
      const opts = extractInlineOptions(last.content)
      return opts.map((label, i) => ({
        label,
        icon: Sparkles,
        style: i === 0 ? 'primary' : 'default',
      }))
    },
  },
]

// Pull a list of clickable options out of an assistant message.
// Handles patterns like:
//   "（例如：欢快流行、安静钢琴、动感电子或大气商务风）"
//   "可选：A、B、C"
//   "你想要 A 还是 B？"
function extractInlineOptions(text) {
  if (!text) return []
  const sources = []
  const paren = text.match(/[（(](?:例如|比如|如|可选|选项|包括)[:：]?\s*([^）)\n]{2,120})[）)]/)
  if (paren) sources.push(paren[1])
  const inline = text.match(/(?:例如|比如|可选|选项)[:：]\s*([^。\n？?！!]{2,120})/)
  if (inline) sources.push(inline[1])
  const eitherOr = text.match(/([^。\n，,：:（(]{1,40}(?:还是|或者?)[^。\n？?！!]{1,80})[？?]/)
  if (eitherOr) sources.push(eitherOr[1])
  for (const raw of sources) {
    const opts = splitOptionString(raw)
    if (opts.length >= 2) return opts
  }
  return []
}

function splitOptionString(raw) {
  return raw
    .replace(/\s*(?:或者|还是|或)\s*/g, '、')
    .split(/[、，,/]/)
    .map(s => s.trim().replace(/^[\s\-·•]+|[\s。等]+$/g, ''))
    .filter(s => s.length >= 2 && s.length <= 18)
}

function QuickReplies({ messages, onSend, disabled }) {
  if (disabled) return null

  // Find first matching rule
  const rule = QUICK_REPLY_RULES.find(r => r.match(messages))
  if (!rule) return null

  const replies = rule.extract ? rule.extract(messages) : rule.replies
  if (!replies?.length) return null

  return (
    <div className="flex flex-wrap gap-2 py-3 animate-fade-in">
      {replies.map(({ label, icon: Icon, style }) => (
        <button
          key={label}
          onClick={() => onSend(label)}
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-medium transition-all duration-150 ${
            style === 'primary'
              ? 'text-white shadow-sm hover:shadow-md active:scale-95'
              : 'bg-white border border-[rgba(0,0,0,0.08)] text-text-light hover:text-text hover:border-[rgba(0,0,0,0.15)]'
          }`}
          style={style === 'primary' ? { background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))' } : undefined}
        >
          {Icon && <Icon size={13} />}
          {label}
        </button>
      ))}
    </div>
  )
}


// =========================================================================
// Welcome Screen
// =========================================================================

function WelcomeScreen({ onSuggestion }) {
  const suggestions = [
    { icon: Music, text: '帮我创作一首欢快的夏日流行歌', sub: '歌词 + 编曲一站搞定' },
    { icon: Mic, text: '把这段文字转成语音朗读', sub: '多种声线可选' },
    { icon: Sparkles, text: '设计一个成熟稳重的男性配音', sub: 'AI 声音设计' },
    { icon: AudioWaveform, text: '我需要一段30秒的背景音乐', sub: '自定义风格和时长' },
  ]

  return (
    <div className="flex flex-col items-center justify-center h-full animate-fade-in px-2">
      <div className="inline-flex p-3 lg:p-3.5 rounded-2xl mb-4 lg:mb-5" style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))' }}>
        <Sparkles size={26} className="text-white" strokeWidth={2} />
      </div>
      <h2 className="text-xl lg:text-2xl font-bold text-text mb-1.5 text-center">嗨，我是 Lyra</h2>
      <p className="text-xs lg:text-sm text-text-muted mb-6 lg:mb-10 text-center px-3">你的 AI 音乐创作伙伴 · 用自然语言描述你的需求</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 lg:gap-3 max-w-lg w-full">
        {suggestions.map(({ icon: Icon, text, sub }) => (
          <button
            key={text}
            onClick={() => onSuggestion(text)}
            className="group/card flex items-start gap-3 sm:flex-col sm:items-start sm:gap-2 p-3.5 sm:p-4 rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white hover:border-[var(--color-primary)] active:border-[var(--color-primary)] hover:shadow-md transition-all duration-200 text-left min-h-[64px]"
          >
            <Icon size={18} className="text-text-muted group-hover/card:text-primary transition-colors flex-shrink-0 mt-0.5 sm:mt-0" />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-text leading-snug">{text}</p>
              <p className="text-xs text-text-muted mt-0.5">{sub}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}


// =========================================================================
// Chat Bubble — with copy, long-text collapse/expand
// =========================================================================

const USER_COLLAPSE_CHARS = 200
const USER_COLLAPSE_LINES = 4

function shouldCollapse(text, charLimit, lineLimit) {
  if (!text) return false
  return text.length > charLimit || text.split('\n').length > lineLimit
}

function ChatBubble({ message }) {
  const { role, content } = message
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(content || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (role === 'user') {
    const needsCollapse = shouldCollapse(content, USER_COLLAPSE_CHARS, USER_COLLAPSE_LINES)
    return (
      <div className="chat-msg-row justify-end animate-fade-in">
        <div className="flex flex-col items-end max-w-[75%]">
          <div className="chat-bubble-user">
            <div className={`chat-bubble-user-inner ${needsCollapse && !expanded ? 'chat-text-collapsed-user' : ''}`}>
              {content}
            </div>
            {needsCollapse && (
              <button onClick={() => setExpanded(e => !e)} className="chat-expand-btn chat-expand-btn-user">
                {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                <span>{expanded ? '收起' : '展开'}</span>
              </button>
            )}
          </div>
          {/* Action buttons */}
          <div className="chat-bubble-actions chat-bubble-actions-right">
            <button onClick={handleCopy} className="chat-action-btn" title="复制">
              {copied ? <Check size={13} className="text-success" /> : <Copy size={13} />}
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (role === 'assistant') {
    return (
      <div className="chat-msg-row animate-fade-in">
        <div className="chat-avatar chat-avatar-ai">
          <Sparkles size={14} />
        </div>
        <div className="chat-msg-body">
          <div className="chat-bubble-ai">
            <div className="agent-md">
              {content ? <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown> : (
                <div className="flex items-center gap-1.5">
                  <span className="chat-typing-cursor" />
                </div>
              )}
            </div>
          </div>
          {/* Action buttons */}
          {content && (
            <div className="chat-bubble-actions chat-bubble-actions-left">
              <button onClick={handleCopy} className="chat-action-btn" title="复制">
                {copied ? <Check size={13} className="text-success" /> : <Copy size={13} />}
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  if (role === 'tool_result') {
    return <ToolResultBubble message={message} />
  }

  return null
}


// =========================================================================
// Tool Result Bubble (collapsible)
// =========================================================================

function ToolResultBubble({ message }) {
  const { content, result, tool_name, credits_cost } = message
  const meta = TOOL_META[tool_name] || { label: tool_name, Icon: Wrench, gradient: 'from-slate-500 to-gray-500' }
  const [expanded, setExpanded] = useState(!AUTO_COLLAPSE_TOOLS.has(tool_name))

  // Failure branch — render error + refund info before any success rendering
  if (result?.error) {
    const refunded = result.refunded || 0
    const refundedFree = result.refunded_free || 0
    return (
      <div className="max-w-[90%] animate-fade-in py-2">
        <div className="rounded-2xl border border-rose-200 bg-rose-50/70 px-4 py-3">
          <div className="flex items-start gap-2.5">
            <div className="neu-icon-tile" style={{ background: 'rgba(244,63,94,0.1)' }}>
              <AlertCircle size={14} className="text-rose-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-rose-800 mb-1">
                {meta.label}：执行失败
              </div>
              <div className="text-xs text-rose-700 break-all">{result.error}</div>
              {refunded > 0 && (
                <div className="mt-1.5 text-[11px] text-emerald-700 inline-flex items-center gap-1">
                  <Coins size={10} />
                  已退款 {refunded} 积分
                  {refundedFree > 0 && `（含签到 ${refundedFree}）`}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  const audioUrlRaw = result?.audio_url
  const trialAudio = result?.trial_audio_url
  const lyrics = result?.lyrics
  const taskId = result?.task_id
  const voiceId = result?.voice_id
  const batchDetails = result?.details && result?.segments_count

  const isBatchResult = tool_name === 'batch_voice_over' && batchDetails
  const isVoiceAsset = (tool_name === 'clone_voice' || tool_name === 'design_voice') && !!voiceId
  const isVoiceList  = tool_name === 'list_voices' && Array.isArray(result?.voices)
  const isEstimate   = tool_name === 'estimate_cost' && (result?.estimated_cost !== undefined || Array.isArray(result?.models))
  const isTaskStatus = tool_name === 'query_task_status' && !!result?.status

  // Main audio url — exclude trial audio when rendered as voice asset
  const audioUrl = isVoiceAsset ? null : (audioUrlRaw || trialAudio)

  // batch_voice_over: details collapsible + standalone audio card
  if (isBatchResult) {
    return (
      <div className="max-w-[90%] animate-fade-in space-y-3 py-2">
        {/* Batch details — collapsible */}
        <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white overflow-hidden">
          <div
            className="flex items-center gap-2.5 px-4 py-3 cursor-pointer select-none hover:bg-[var(--color-surface-light)] transition-colors"
            onClick={() => setExpanded(!expanded)}
          >
            <div className="neu-icon-tile">
              <meta.Icon size={14} />
            </div>
            <span className="text-xs font-semibold text-text">{meta.label}</span>
            <span className="chip-status chip-done">
              <Check size={10} strokeWidth={3} />
              完成
            </span>
            <div className="ml-auto flex items-center gap-2">
              {credits_cost > 0 && (
                <span className="inline-flex items-center gap-1 text-[11px] text-text-muted"><Coins size={10} /> -{credits_cost}</span>
              )}
              <ChevronDown
                size={14}
                className={`text-text-muted transition-transform duration-200 ${expanded ? '' : '-rotate-90'}`}
              />
            </div>
          </div>
          {expanded && (
            <div className="px-4 pb-4 border-t border-[rgba(0,0,0,0.04)]">
              <div className="rounded-xl p-3 mt-3 text-xs"
                style={{ background: 'var(--color-surface-light)' }}>
                <p className="font-medium text-text mb-2">{result.segments_count} 段 · {result.total_chars} 字</p>
                <div className="space-y-1.5">
                  {result.details.map((d, i) => (
                    <div key={i} className="flex items-center gap-2.5">
                      <img
                        src={`https://api.dicebear.com/7.x/shapes/svg?seed=${encodeURIComponent(d.role || d.voice_id || i)}&backgroundColor=b6e3f4,c0aede,ffd5dc,c0f5d4,ffe5b4`}
                        alt=""
                        loading="lazy"
                        className="voice-avatar w-7 h-7"
                      />
                      <span className="font-medium text-text w-14 flex-shrink-0">{d.role}</span>
                      <span className="text-primary font-mono text-[11px] truncate flex-1">{d.voice_id}</span>
                      <span className="text-text-muted text-[11px] flex-shrink-0">{d.chars}字</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Audio result — standalone card, always visible */}
        {audioUrl && (
          <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white overflow-hidden">
            <div className="px-4 py-3 flex items-center gap-2.5">
              <div className="neu-icon-tile">
                <Volume2 size={14} />
              </div>
              <span className="text-xs font-semibold text-text">配音结果</span>
            </div>
            <div className="px-4 pb-4">
              <AudioPlayer src={audioUrl} />
            </div>
          </div>
        )}
      </div>
    )
  }

  // Voice asset — clone_voice / design_voice
  if (isVoiceAsset) {
    return (
      <div className="max-w-[90%] animate-fade-in py-2">
        <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white overflow-hidden">
          <div className="flex items-center gap-2.5 px-4 py-3">
            <div className="neu-icon-tile"><meta.Icon size={14} /></div>
            <span className="text-xs font-semibold text-text">{meta.label}</span>
            <span className="chip-status chip-done">
              <Check size={10} strokeWidth={3} />
              已创建
            </span>
            {credits_cost > 0 && (
              <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-text-muted"><Coins size={10} /> -{credits_cost}</span>
            )}
          </div>
          <div className="px-4 pb-4 space-y-3">
            <div className="flex items-center gap-3 p-3 rounded-xl" style={{ background: 'var(--color-surface-light)', boxShadow: 'inset 2px 2px 4px rgba(0,0,0,.04)' }}>
              <img
                src={`https://api.dicebear.com/7.x/bottts/svg?seed=${encodeURIComponent(voiceId)}&backgroundColor=b6e3f4,c0aede,d1d4f9&radius=20`}
                alt=""
                loading="lazy"
                className="voice-avatar w-12 h-12"
              />
              <div className="min-w-0 flex-1">
                <div className="text-[10px] text-text-muted mb-0.5">新音色 ID</div>
                <div className="flex items-center gap-1.5">
                  <code className="text-[12.5px] font-mono font-semibold text-text truncate">{voiceId}</code>
                  <button
                    onClick={() => navigator.clipboard.writeText(voiceId)}
                    className="h-6 w-6 grid place-items-center rounded text-text-muted hover:text-primary cursor-pointer flex-shrink-0 bg-white"
                    style={{ boxShadow: '2px 2px 4px rgba(0,0,0,.06)' }}
                    title="复制"
                  >
                    <Copy size={12} />
                  </button>
                </div>
              </div>
            </div>

            {trialAudio && (
              <div>
                <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-2">试听</p>
                <AudioPlayer src={trialAudio} />
              </div>
            )}

            <div className="flex items-center gap-2 p-2.5 rounded-xl" style={{ background: '#f0fdf4' }}>
              <Check size={14} className="text-success flex-shrink-0" />
              <span className="text-[12px] text-text">已加入音色库，可在后续 TTS 任务中直接复用</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Voice library — list_voices
  if (isVoiceList) {
    const voices = result.voices
    return (
      <div className="max-w-[90%] animate-fade-in py-2">
        <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white overflow-hidden">
          <div
            className="flex items-center gap-2.5 px-4 py-3 cursor-pointer select-none hover:bg-[var(--color-surface-light)] transition-colors"
            onClick={() => setExpanded(!expanded)}
          >
            <div className="neu-icon-tile"><meta.Icon size={14} /></div>
            <span className="text-xs font-semibold text-text">{meta.label}</span>
            <span className="text-[11px] text-text-muted">共 {voices.length} 个</span>
            <ChevronDown
              size={14}
              className={`ml-auto text-text-muted transition-transform duration-200 ${expanded ? '' : '-rotate-90'}`}
            />
          </div>
          {expanded && voices.length > 0 && (
            <div className="px-2 pb-2 border-t border-[rgba(0,0,0,0.04)] max-h-[260px] overflow-y-auto">
              {voices.map((v, i) => {
                const vType = v.voice_type || 'system'
                const avatarStyle = vType === 'system' ? 'shapes' : 'bottts'
                const typeLabel = vType === 'system' ? '系统' : vType === 'cloned' ? '克隆' : vType === 'designed' ? '设计' : vType
                return (
                  <div key={v.voice_id || i} className="flex items-center gap-2.5 p-2 rounded-xl hover:bg-[var(--color-surface-light)] transition group">
                    <img
                      src={`https://api.dicebear.com/7.x/${avatarStyle}/svg?seed=${encodeURIComponent(v.voice_id || i)}&backgroundColor=b6e3f4,c0aede,ffd5dc,c0f5d4,ffe5b4`}
                      alt=""
                      loading="lazy"
                      className="voice-avatar w-9 h-9"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[12.5px] font-medium text-text truncate">
                          {v.voice_name || v.voice_id}
                        </span>
                        <span className="px-1.5 py-0 rounded text-[9px] font-semibold text-text-muted bg-[var(--color-surface)]">
                          {typeLabel}
                        </span>
                      </div>
                      <code className="text-[10px] font-mono text-text-muted">{v.voice_id}</code>
                    </div>
                    <button
                      onClick={() => navigator.clipboard.writeText(v.voice_id)}
                      className="h-6 w-6 grid place-items-center rounded text-text-muted hover:text-primary cursor-pointer shrink-0 opacity-0 group-hover:opacity-100 transition"
                      title="复制 voice_id"
                    >
                      <Copy size={12} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    )
  }

  // Cost estimate — estimate_cost
  if (isEstimate) {
    const cost = result.estimated_cost
    const models = Array.isArray(result.models) ? result.models : null
    const hasMultipleModels = models && models.length > 1
    const cheapest = hasMultipleModels ? Math.min(...models.map(m => Number(m.cost) || 0)) : null
    return (
      <div className="max-w-[90%] animate-fade-in py-2">
        <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white overflow-hidden">
          <div
            className={`flex items-center gap-2.5 px-4 py-3 select-none ${hasMultipleModels ? 'cursor-pointer hover:bg-[var(--color-surface-light)] transition-colors' : ''}`}
            onClick={() => hasMultipleModels && setExpanded(!expanded)}
          >
            <div className="neu-icon-tile"><meta.Icon size={14} /></div>
            <span className="text-xs font-semibold text-text">{meta.label}</span>
            {cost !== undefined && (
              <span className="inline-flex items-center gap-1 text-[13px] font-bold text-success ml-1">
                <Coins size={12} className="text-warning" />{cost}
              </span>
            )}
            {hasMultipleModels && (
              <ChevronDown
                size={14}
                className={`ml-auto text-text-muted transition-transform duration-200 ${expanded ? '' : '-rotate-90'}`}
              />
            )}
          </div>
          {expanded && hasMultipleModels && (
            <div className="px-4 pb-4 border-t border-[rgba(0,0,0,0.04)]">
              <div className="grid grid-cols-3 gap-2 mt-3">
                {models.slice(0, 3).map((m, i) => {
                  const isCheapest = Number(m.cost) === cheapest
                  return (
                    <div
                      key={m.id || m.name || i}
                      className="relative rounded-xl p-3 text-center transition hover:-translate-y-0.5"
                      style={{
                        boxShadow: isCheapest
                          ? '3px 3px 7px rgba(34,197,94,0.15), inset 0 0 0 1.5px rgba(34,197,94,0.25)'
                          : '3px 3px 7px rgba(0,0,0,.06), -3px -3px 7px rgba(255,255,255,.9)',
                        background: isCheapest ? 'linear-gradient(145deg, #ecfdf5, #d1fae5)' : 'white',
                      }}
                    >
                      {isCheapest && (
                        <span className="absolute -top-1.5 -right-1.5 text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-success text-white">推荐</span>
                      )}
                      <div className="text-[10px] font-mono text-text-muted truncate">{m.id || m.name}</div>
                      <div className={`text-[20px] font-bold mt-1 ${isCheapest ? 'text-success' : 'text-text'}`}>{m.cost}</div>
                      <div className="text-[10px] text-text-light">{m.unit || '积分'}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Task status — query_task_status (inline row)
  if (isTaskStatus) {
    const { status, task_id, file_id } = result
    const normalized = String(status).toLowerCase()
    const isCompleted = normalized === 'completed' || normalized === 'success'
    const isFailed = normalized === 'failed' || normalized === 'error'
    const isProcessing = !isCompleted && !isFailed
    return (
      <div className="max-w-[90%] animate-fade-in py-2">
        <div className="flex items-center gap-3 px-3.5 py-2.5 rounded-2xl bg-white border border-[rgba(0,0,0,0.06)]">
          <div className="neu-icon-tile">
            {isProcessing ? <Loader2 size={14} className="animate-spin" /> : <meta.Icon size={14} />}
          </div>
          <span className="text-[12.5px] text-text">任务状态</span>
          {task_id && (
            <code className="text-[11px] font-mono text-text-muted px-1.5 py-0.5 rounded bg-[var(--color-surface-light)] truncate max-w-[140px]">{task_id}</code>
          )}
          {file_id != null && (
            <span className="text-[11px] text-text-muted">· file: {file_id}</span>
          )}
          <span className={`ml-auto chip-status ${isCompleted ? 'chip-done' : isFailed ? 'chip-failed' : 'chip-processing'}`}>
            {isProcessing && <span className="pulse-dot" style={{ background: '#f59e0b' }}></span>}
            {status}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-[90%] animate-fade-in py-2">
      <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white overflow-hidden">
        {/* Header — clickable to toggle */}
        <div
          className="flex items-center gap-2.5 px-4 py-3 cursor-pointer select-none hover:bg-[var(--color-surface-light)] transition-colors"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="neu-icon-tile">
            <meta.Icon size={14} />
          </div>
          <span className="text-xs font-semibold text-text">{meta.label}</span>
          <span className="chip-status chip-done">
            <Check size={10} strokeWidth={3} />
            完成
          </span>
          <div className="ml-auto flex items-center gap-2">
            {credits_cost > 0 && (
              <span className="inline-flex items-center gap-1 text-[11px] text-text-muted"><Coins size={10} /> -{credits_cost}</span>
            )}
            <ChevronDown
              size={14}
              className={`text-text-muted transition-transform duration-200 ${expanded ? '' : '-rotate-90'}`}
            />
          </div>
        </div>

        {/* Collapsible content */}
        {expanded && (
          <div className="px-4 pb-4 border-t border-[rgba(0,0,0,0.04)]">
            {lyrics && (
              <div className="rounded-xl p-3 mt-3 text-xs text-text leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto"
                style={{ background: 'var(--color-surface-light)' }}>
                {result.song_title && <p className="font-semibold mb-1">{result.song_title}</p>}
                {result.style_tags && <p className="text-text-muted mb-2">{result.style_tags}</p>}
                {lyrics}
              </div>
            )}

            {audioUrl && <div className="mt-3"><AudioPlayer src={audioUrl} title={result.song_title} /></div>}

            {taskId && (
              <div className="text-xs text-text-muted mt-3">
                异步任务已提交，任务ID: <code className="text-primary">{taskId}</code>
              </div>
            )}

            {!lyrics && !audioUrl && !taskId && (
              <pre className="text-xs text-text-muted whitespace-pre-wrap max-h-32 overflow-y-auto mt-3">
                {typeof content === 'string' ? content : JSON.stringify(result || content, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  )
}


// =========================================================================
// Tool Confirmation Card (inline in chat)
// =========================================================================

// Tools that support duration selection
const DURATION_TOOLS = new Set(['generate_lyrics', 'generate_music', 'generate_cover'])
const DURATION_OPTIONS = [
  { id: 'short', label: '短', desc: '20-40秒', sub: '适合短视频/片头' },
  { id: 'medium', label: '中', desc: '1-2分钟', sub: '适合BGM/配乐' },
  { id: 'standard', label: '标准', desc: '2-3分钟', sub: '完整歌曲' },
  { id: 'long', label: '长', desc: '3-4分钟', sub: '丰富编排' },
]

function VoiceDirectorBadge({ summary }) {
  const [expanded, setExpanded] = useState(false)
  if (!summary) return null

  const { director_used, reason, changed_count, total, diff } = summary

  if (!director_used && reason === 'llm_review_failed') {
    return (
      <div className="mb-3 px-3 py-2 rounded-xl border border-amber-200 bg-amber-50 text-amber-700 text-xs flex items-center gap-2">
        <Sparkles size={12} />
        AI 精修调用失败，已使用基础参数继续
      </div>
    )
  }

  if (!director_used || !changed_count) return null

  return (
    <div className="mb-3 rounded-xl border border-emerald-200 bg-emerald-50 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-emerald-800 hover:bg-emerald-100/60 transition-colors"
      >
        <Sparkles size={12} />
        <span className="font-medium">AI 导演已微调 {changed_count}/{total} 段参数</span>
        <ChevronDown
          size={12}
          className={`ml-auto transition-transform ${expanded ? '' : '-rotate-90'}`}
        />
      </button>
      {expanded && (
        <div className="px-3 pb-2.5 pt-1 space-y-1 max-h-48 overflow-y-auto border-t border-emerald-200/60">
          {diff.map((entry) => (
            <div key={entry.index} className="text-[11px] text-emerald-900/80">
              <span className="font-mono mr-1.5 text-emerald-700">#{entry.index + 1}</span>
              <span className="font-medium mr-1">{entry.role}:</span>
              {Object.entries(entry.changes).map(([field, val]) => (
                <span key={field} className="inline-flex items-center gap-0.5 mr-2">
                  <span className="text-emerald-600">{field}</span>
                  <span className="text-text-muted">{String(val.from ?? '—')} → {String(val.to ?? '—')}</span>
                </span>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ToolConfirmCard({ msg, userCredits, userFreeCredits, onConfirm, onCancel, disabled }) {
  const { tool_name, params, models, status } = msg
  const clearRoleVoiceMemory = useAgentStore((state) => state.clearRoleVoiceMemory)
  const meta = TOOL_META[tool_name] || { label: tool_name, Icon: Wrench, gradient: 'from-slate-500 to-gray-500' }
  const hasModelChoice = models && models.length > 1
  const showDuration = DURATION_TOOLS.has(tool_name)
  const recommendMap = MODEL_RECOMMENDATION[tool_name] || null
  const voiceDirector = params?.voice_director
  const [selectedModel, setSelectedModel] = useState(
    params?.model || (models?.[0]?.id ?? null)
  )
  const [selectedDuration, setSelectedDuration] = useState(
    params?.target_duration || 'standard'
  )

  const selectedModelEntry = models?.find((m) => m.id === selectedModel) ?? models?.[0]
  const selectedCost = selectedModelEntry?.cost ?? '?'
  const selectedIsPerChar = selectedModelEntry?.billing_unit === 'per_10k_chars'
  const selectedCostLabel = selectedCost === '?' ? '' : (selectedIsPerChar ? `约 ${selectedCost}积分` : `${selectedCost}积分`)
  const isBatch = tool_name === 'batch_voice_over'
  const voiceSelection = params?.voice_selection
  const roleOptions = voiceSelection?.roles || []
  const [roleSelections, setRoleSelections] = useState(() => buildInitialRoleSelections(voiceSelection))
  const [expandedRoles, setExpandedRoles] = useState(() => {
    const firstRole = roleOptions[0]?.role
    return firstRole ? { [firstRole]: true } : {}
  })
  const toggleRole = (role) => {
    setExpandedRoles((current) => ({ ...current, [role]: !current[role] }))
  }

  // Executing state
  if (status === 'executing') {
    return (
      <div className="max-w-[90%] animate-fade-in py-2">
        <div className="flex items-center gap-3 px-3.5 py-2.5 rounded-2xl bg-white border border-[rgba(0,0,0,0.06)]">
          <div className="neu-icon-tile">
            <meta.Icon size={14} />
          </div>
          <span className="text-[12.5px] font-medium text-text">{meta.label}</span>
          <span className="ml-auto chip-status chip-processing">
            <span className="pulse-dot" style={{ background: '#f59e0b' }}></span>
            执行中
          </span>
        </div>
      </div>
    )
  }

  // Param summary — special handling for batch_voice_over
  const segments = isBatch ? (params?.segments || []) : []
  const totalChars = segments.reduce((sum, s) => sum + (s.text?.length || 0), 0)

  const paramEntries = isBatch
    ? []  // batch shows segments separately
    : Object.entries(params || {})
        .filter(([k]) => !['model', 'sample_rate', 'bitrate', 'audio_format', 'target_duration'].includes(k))
  const paramLines = paramEntries.map(([k, v]) => {
    const label = { prompt: '描述', text: '文本', lyrics: '歌词', voice_id: '音色', theme: '主题', mode: '模式', is_instrumental: '纯器乐', emotion: '情感', speed: '语速' }[k] || k
    const val = typeof v === 'string' && v.length > 80 ? v.slice(0, 80) + '...' : String(v)
    return { label, val }
  })

  const handleConfirm = () => {
    const extra = showDuration ? { target_duration: selectedDuration } : undefined
    onConfirm(selectedModel, extra)
  }
  const handleRoleSelectionChange = (role, voiceId) => {
    setRoleSelections((current) => ({ ...current, [role]: voiceId }))
  }
  const handleBatchConfirm = () => {
    onConfirm(selectedModel, buildVoiceSelectionOverrides(params, roleSelections))
  }

  return (
    <div className="max-w-[90%] animate-fade-in py-2">
      <div className="rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white overflow-hidden">
        <div className="p-5">
          {/* Header */}
          <div className="flex items-center gap-2.5 mb-4">
            <div className="neu-icon-tile neu-icon-tile-lg">
              <meta.Icon size={18} />
            </div>
            <div>
              <span className="text-sm font-semibold text-text">{meta.label}</span>
              <span className="text-xs text-text-muted ml-2">· 请确认</span>
            </div>
            <span className="ml-auto chip-status chip-pending">待确认</span>
          </div>

          {/* Params */}
          {paramLines.length > 0 && (
            <div className="rounded-xl p-3 mb-3 text-xs space-y-1.5"
              style={{ background: 'var(--color-surface-light)' }}>
              {paramLines.map(({ label, val }) => (
                <div key={label} className="flex gap-2">
                  <span className="text-text-muted flex-shrink-0 w-12 text-right">{label}</span>
                  <span className="text-text">{val}</span>
                </div>
              ))}
            </div>
          )}

          {/* Batch segments summary — with inline voice casting when candidates are available */}
          {isBatch && segments.length > 0 && (
            <div className="rounded-xl p-3 mb-3 text-xs" style={{ background: 'var(--color-surface-light)' }}>
              <p className="font-medium text-text mb-2">{segments.length} 段 · {totalChars} 字</p>
              {roleOptions.length > 0 ? (
                <div className="space-y-2">
                  {roleOptions.map((roleItem) => {
                    const selectedVoiceId = roleSelections[roleItem.role]
                    const expanded = !!expandedRoles[roleItem.role]
                    const selectedCandidate = roleItem.candidates?.find((c) => c.voice_id === selectedVoiceId)
                    const selectedTitle = selectedCandidate?.voice_name || selectedCandidate?.voice_id || selectedVoiceId || '未选择'
                    return (
                      <section key={roleItem.role} className="border border-[rgba(0,0,0,0.06)] rounded-lg overflow-hidden bg-white">
                        <button
                          type="button"
                          onClick={() => toggleRole(roleItem.role)}
                          disabled={disabled}
                          className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[var(--color-surface-light)] transition-colors disabled:cursor-not-allowed"
                        >
                          <ChevronDown size={12} className={`text-text-muted flex-shrink-0 transition-transform ${expanded ? '' : '-rotate-90'}`} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-semibold text-text">{roleItem.role}</span>
                              {roleItem.from_memory && (
                                <span
                                  title="沿用之前会话的音色记忆"
                                  className="inline-flex items-center gap-0.5 text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded"
                                >
                                  <Bookmark size={9} />
                                  记忆
                                </span>
                              )}
                              {roleItem.role_summary && (
                                <span className="text-[11px] text-text-muted truncate">{roleItem.role_summary}</span>
                              )}
                            </div>
                            <p className="text-[11px] text-text-light mt-0.5">
                              当前: <span className="text-primary font-medium">{selectedTitle}</span>
                            </p>
                          </div>
                        </button>
                        {expanded && (
                          <div className="px-3 pb-3 pt-1 space-y-1.5 border-t border-[rgba(0,0,0,0.04)]">
                            {roleItem.from_memory && !disabled && (
                              <button
                                type="button"
                                onClick={() => clearRoleVoiceMemory(api, roleItem.role)}
                                className="text-[11px] text-text-muted hover:text-rose-600 transition-colors inline-flex items-center gap-1 pt-2"
                              >
                                <X size={10} />
                                清除此角色记忆，下次由 AI 重新挑选
                              </button>
                            )}
                            {roleItem.sample_text && (
                              <p className="text-[11px] text-text-light leading-relaxed pt-2 pb-1">
                                示例：{roleItem.sample_text}
                              </p>
                            )}
                            {roleItem.candidates?.map((candidate, index) => {
                              const selected = selectedVoiceId === candidate.voice_id
                              const title = candidate.voice_name || candidate.voice_id
                              return (
                                <button
                                  key={candidate.voice_id}
                                  type="button"
                                  onClick={() => handleRoleSelectionChange(roleItem.role, candidate.voice_id)}
                                  disabled={disabled}
                                  className={`w-full text-left border rounded-lg px-2.5 py-2 transition-all disabled:opacity-50 ${
                                    selected
                                      ? 'border-primary bg-[rgba(99,102,241,0.06)]'
                                      : 'border-[rgba(0,0,0,0.06)] bg-white hover:border-[rgba(0,0,0,0.15)]'
                                  }`}
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0 flex-1">
                                      <div className="flex items-center gap-1.5 flex-wrap">
                                        <span className="text-xs font-medium text-text">{title}</span>
                                        {index === 0 && (
                                          <span className="inline-flex items-center gap-0.5 text-[10px] text-primary bg-[rgba(99,102,241,0.08)] px-1.5 py-0.5 rounded">
                                            <Sparkles size={9} />
                                            推荐
                                          </span>
                                        )}
                                      </div>
                                      {candidate.intro && (
                                        <p className="text-[11px] text-text-muted mt-0.5 leading-relaxed">{candidate.intro}</p>
                                      )}
                                      {candidate.reason && (
                                        <p className="text-[11px] text-text-light mt-0.5 leading-relaxed">{candidate.reason}</p>
                                      )}
                                    </div>
                                    {selected && (
                                      <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-primary text-white flex-shrink-0 mt-0.5">
                                        <Check size={10} />
                                      </span>
                                    )}
                                  </div>
                                </button>
                              )
                            })}
                          </div>
                        )}
                      </section>
                    )
                  })}
                </div>
              ) : (
                <div className="max-h-48 overflow-y-auto">
                  {segments.map((s, i) => (
                    <div key={i} className="flex items-center gap-2 py-0.5 text-text-muted">
                      <span className="font-medium text-text w-14 text-right flex-shrink-0">{s.role}</span>
                      <span className="text-primary flex-shrink-0">{s.voice_id}</span>
                      <span className="truncate flex-1">{s.text?.slice(0, 30)}{s.text?.length > 30 ? '...' : ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Duration selector (for music tools) */}
          {showDuration && (
            <div className="mb-3">
              <p className="text-xs font-medium text-text-light mb-2">选择时长：</p>
              <div className="grid grid-cols-4 gap-2">
                {DURATION_OPTIONS.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => setSelectedDuration(d.id)}
                    className={`flex flex-col items-center px-2 py-2 text-xs gap-0.5 rounded-xl border transition-all duration-150 cursor-pointer ${
                      selectedDuration === d.id
                        ? 'border-primary bg-[rgba(99,102,241,0.06)] text-primary font-semibold'
                        : 'border-[rgba(0,0,0,0.06)] bg-white text-text-light hover:border-[rgba(0,0,0,0.12)]'
                    }`}
                  >
                    <span className="font-medium">{d.label}</span>
                    <span className="text-text-muted" style={{ fontSize: '10px' }}>{d.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Model selection */}
          {hasModelChoice && (
            <div className="mb-3">
              <p className="text-xs font-medium text-text-light mb-2">选择模型：</p>
              <div className="flex gap-2 flex-wrap">
                {models.map((m) => {
                  const isPerChar = m.billing_unit === 'per_10k_chars'
                  const hasChars = isPerChar && (m.char_count ?? 0) > 0
                  const recommendation = recommendMap?.[m.id]
                  return (
                    <button
                      key={m.id}
                      onClick={() => setSelectedModel(m.id)}
                      className={`flex flex-col items-start px-3 py-2 text-xs gap-0.5 rounded-xl border transition-all duration-150 cursor-pointer ${
                        selectedModel === m.id
                          ? 'border-primary bg-[rgba(99,102,241,0.06)] text-primary font-semibold'
                          : 'border-[rgba(0,0,0,0.06)] bg-white text-text-light hover:border-[rgba(0,0,0,0.12)]'
                      }`}
                    >
                      <span>{m.name}</span>
                      {m.description && (
                        <span className="text-text-muted" style={{ fontSize: '10px' }}>{m.description}</span>
                      )}
                      <span className="flex items-center gap-0.5 text-text-muted">
                        <Coins size={10} />
                        {isPerChar && hasChars
                          ? <>约 {m.cost} 积分 <span className="text-[10px] opacity-70">（{m.char_count}字 · {m.unit_cost}/万字）</span></>
                          : isPerChar
                            ? <>{m.unit_cost} 积分/万字符</>
                            : <>{m.cost} {m.unit || '积分/次'}</>
                        }
                      </span>
                      {recommendation && (
                        <span className="inline-flex items-center gap-0.5 mt-0.5 text-[10px] text-primary bg-[rgba(99,102,241,0.08)] px-1.5 py-0.5 rounded">
                          <Sparkles size={9} />
                          {recommendation}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Single model — just show price */}
          {!hasModelChoice && models?.length === 1 && (() => {
            const m = models[0]
            const isPerChar = m.billing_unit === 'per_10k_chars'
            const hasChars = isPerChar && (m.char_count ?? 0) > 0
            return (
              <div className="mb-3 flex items-center gap-2 text-xs text-text-light">
                <Coins size={12} className="text-primary" />
                {isPerChar && hasChars ? (
                  <span>预估费用: <strong className="text-text">约 {m.cost} 积分</strong> <span className="text-text-muted">（{m.char_count} 字 × {m.unit_cost}/万字符）</span></span>
                ) : isPerChar ? (
                  <span>单价: <strong className="text-text">{m.unit_cost} 积分/万字符</strong></span>
                ) : (
                  <span>费用: <strong className="text-text">{m.cost} {m.unit || '积分/次'}</strong></span>
                )}
              </div>
            )
          })()}

          {/* Voice director diff — shown when _enforce_emotion_diversity modified segments */}
          {voiceDirector && <VoiceDirectorBadge summary={voiceDirector} />}

          {/* Divider + Actions */}
          <div className="border-t border-[rgba(0,0,0,0.04)] pt-3 mt-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">
                余额: {userCredits} + {userFreeCredits} 签到
              </span>
              <div className="flex gap-2">
                <button onClick={onCancel} disabled={disabled} className="px-4 py-2 text-xs rounded-xl border border-[rgba(0,0,0,0.08)] bg-white text-text-light hover:bg-[var(--color-surface)] transition-colors disabled:opacity-50">
                  跳过
                </button>
                {isBatch && roleOptions.length > 0 ? (
                  <button
                    onClick={handleBatchConfirm}
                    disabled={disabled}
                    className="px-4 py-2 text-xs rounded-xl text-white font-medium gap-1 inline-flex items-center disabled:opacity-50 transition-all hover:brightness-110"
                    style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))' }}
                  >
                    确认并配音
                    {selectedCost !== '?' && <span>· {selectedCostLabel}</span>}
                  </button>
                ) : (
                  <button
                    onClick={handleConfirm}
                    disabled={disabled}
                    className="px-4 py-2 text-xs rounded-xl text-white font-medium gap-1 inline-flex items-center disabled:opacity-50 transition-all hover:brightness-110"
                    style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))' }}
                  >
                    确认执行
                    {selectedCost !== '?' && <span>· {selectedCostLabel}</span>}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
