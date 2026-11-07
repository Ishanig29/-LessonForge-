import { Route, Routes } from 'react-router-dom'
import { EmptyState } from './components/ui'
import { AppLayout } from './layouts/AppLayout'
import CreateLesson from './pages/CreateLesson'
import Dashboard from './pages/Dashboard'
import LessonWorkspace from './pages/LessonWorkspace'
import MyLessons from './pages/MyLessons'
import ResearchLibrary from './pages/ResearchLibrary'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="create" element={<CreateLesson />} />
        <Route path="lessons" element={<MyLessons />} />
        <Route path="lessons/:id" element={<LessonWorkspace />} />
        <Route path="library" element={<ResearchLibrary />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<EmptyState title="Page not found">Use the sidebar to find your way back.</EmptyState>} />
      </Route>
    </Routes>
  )
}
