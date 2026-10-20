import { Navigate, Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Footer } from "./components/Footer";
import { Home } from "./pages/Home";
import { ProjectsIndex } from "./pages/ProjectsIndex";
import { ProjectDetail } from "./pages/ProjectDetail";
import { Services } from "./pages/Services";
import { Contact } from "./pages/Contact";
import { NotFound } from "./pages/NotFound";
import { ChurnSandbox } from "./demos/ChurnSandbox";

export function App() {
  return (
    <>
      <Nav />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/projects" element={<ProjectsIndex />} />
          <Route path="/experiments" element={<ProjectsIndex />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/demos/churn-sandbox" element={<ChurnSandbox />} />
          <Route path="/services" element={<Services />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/about" element={<Navigate to="/services" replace />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </>
  );
}
