import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import useAuthStore from './store/authStore'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import Dashboard from './pages/dashboard/Dashboard'
import MusicCreate from './pages/music/MusicCreate'
import MusicCover from './pages/music/MusicCover'
import SpeechSynth from './pages/speech/SpeechSynth'
import VoiceStudio from './pages/voice/VoiceStudio'
import MyAssets from './pages/assets/MyAssets'
import Workflow from './pages/workflow/Workflow'
import AgentWorkspace from './pages/agent/AgentWorkspace'
import Credits from './pages/billing/Credits'
import History from './pages/billing/History'
import AdminLayout from './pages/admin/AdminLayout'

export default function App() {
  const fetchProfile = useAuthStore((s) => s.fetchProfile)

  useEffect(() => {
    if (localStorage.getItem('access_token')) fetchProfile()
    else useAuthStore.setState({ loading: false })
  }, [])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="assets" element={<MyAssets />} />
          <Route path="music/create" element={<MusicCreate />} />
          <Route path="music/cover" element={<MusicCover />} />
          <Route path="speech" element={<SpeechSynth />} />
          <Route path="voice" element={<VoiceStudio />} />
          <Route path="workflow" element={<Workflow />} />
          <Route path="agent" element={<AgentWorkspace />} />
          <Route path="billing" element={<Credits />} />
          <Route path="billing/history" element={<History />} />
          <Route path="admin/*" element={<ProtectedRoute adminOnly><AdminLayout /></ProtectedRoute>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
