import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Footer } from "./components/Footer";
import { Home } from "./pages/Home";
import { ProjectsIndex } from "./pages/ProjectsIndex";
import { ProjectDetail } from "./pages/ProjectDetail";
import { Services } from "./pages/Services";
import { Contact } from "./pages/Contact";
import { NotFound } from "./pages/NotFound";
import ChurnSandbox from "./demos/churn-sandbox/ChurnSandbox";
import ForecastWorkbench from "./demos/forecast-workbench/ForecastWorkbench";
import HierarchyExplorer from "./demos/hierarchy-explorer/HierarchyExplorer";
import { DemoErrorBoundary } from "./demos/ErrorBoundary";

export function App() {
  const location = useLocation();
  const isDemo = location.pathname.startsWith("/demos/");
  return (
    <>
      <Nav />
      <main className="app-main app-main--fluid">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/projects" element={<ProjectsIndex />} />
          <Route path="/experiments" element={<ProjectsIndex />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route
            path="/demos/churn-sandbox"
            element={
              <DemoErrorBoundary>
                <ChurnSandbox />
              </DemoErrorBoundary>
            }
          />
          <Route
            path="/demos/forecast-workbench"
            element={
              <DemoErrorBoundary>
                <ForecastWorkbench />
              </DemoErrorBoundary>
            }
          />
          <Route
            path="/demos/hierarchy-explorer"
            element={
              <DemoErrorBoundary>
                <HierarchyExplorer />
              </DemoErrorBoundary>
            }
          />
          <Route path="/services" element={<Services />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/about" element={<Navigate to="/services" replace />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      {!isDemo && <Footer />}
    </>
  );
}
