import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import CopyDatabasePage from "./pages/CopyDatabasePage";
import JobsPage from "./pages/JobsPage";
import JobDetailPage from "./pages/JobDetailPage";
import AgentsPage from "./pages/AgentsPage";

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 relative px-8 pt-6 pb-16">
        <Routes>
          <Route path="/" element={<CopyDatabasePage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/:id" element={<JobDetailPage />} />
          <Route path="/agents" element={<AgentsPage />} />
        </Routes>
      </main>
    </div>
  );
}
