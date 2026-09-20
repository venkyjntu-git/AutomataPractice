import { Navigate, Route, Routes } from "react-router-dom"
import PracticePage from "./pages/PracticePage"
import PracticeQuestionPage from "./pages/PracticeQuestionPage"
import AutomataViewerPage from "./pages/AutomataViewerPage"

export default function App() {
  return (
    <Routes>
      <Route path="/practice" element={<PracticePage />} />
      <Route path="/practice/question/:id" element={<PracticeQuestionPage />} />
      <Route path="/automata/viewer/:token" element={<AutomataViewerPage />} />
      <Route path="*" element={<Navigate to="/practice" replace />} />
    </Routes>
  )
}
