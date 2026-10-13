import { Navigate, Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Footer } from "./components/Footer";
import { Home } from "./pages/Home";
import { ProjectsIndex } from "./pages/ProjectsIndex";
import { ProjectDetail } from "./pages/ProjectDetail";
import { RAGChat } from "./pages/RAGChat";
import { Services } from "./pages/Services";

export function App() {
  return (
    <>
      <Nav />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/projects" element={<ProjectsIndex />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/chat" element={<RAGChat />} />
          <Route path="/services" element={<Services />} />
          <Route path="/about" element={<Navigate to="/services" replace />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>
      <Footer />
    </>
  );
}
