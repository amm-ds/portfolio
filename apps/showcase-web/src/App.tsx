import { Suspense, lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Footer } from "./components/Footer";
import { RouteAnnouncer } from "./components/RouteAnnouncer";
import { usePageMeta } from "./seo";
import { Home } from "./pages/Home";
import { ProjectsIndex } from "./pages/ProjectsIndex";
import { NotFound } from "./pages/NotFound";
import { DemoErrorBoundary } from "./demos/ErrorBoundary";

// Route-level code splitting: each page/demo below ships as its own chunk so
// the initial bundle only carries Home + the projects index.
const ProjectDetail = lazy(() =>
  import("./pages/ProjectDetail").then((m) => ({ default: m.ProjectDetail })),
);
const Services = lazy(() =>
  import("./pages/Services").then((m) => ({ default: m.Services })),
);
const Contact = lazy(() =>
  import("./pages/Contact").then((m) => ({ default: m.Contact })),
);
const Glossary = lazy(() =>
  import("./pages/Glossary").then((m) => ({ default: m.Glossary })),
);
const ChurnSandbox = lazy(() => import("./demos/churn-sandbox/ChurnSandbox"));
const ForecastWorkbench = lazy(
  () => import("./demos/forecast-workbench/ForecastWorkbench"),
);

/* Accessibility styles kept here (rather than styles.css) so they travel with
   the shell: skip link, visually-hidden utility, and the route skeleton. */
const SHELL_CSS = `
.skip-link {
  position: absolute;
  left: -10000px;
  top: 0;
  z-index: 200;
  font-family: var(--mono);
  font-size: 0.85rem;
  color: var(--fg, #e6e6e6);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0 0 6px 0;
  padding: 0.5rem 0.9rem;
}
.skip-link:focus {
  left: 0;
  top: 0;
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
.route-skeleton {
  max-width: 60rem;
  margin: 0 auto;
  padding: 2.5rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}
.route-skeleton-line {
  height: 0.85rem;
  border-radius: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  animation: route-skeleton-pulse 1.4s ease-in-out infinite;
}
.route-skeleton-title { height: 1.7rem; width: 40%; }
.route-skeleton-panel {
  margin-top: 1rem;
  padding: 1.2rem;
  border: 1px dashed var(--border);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.route-skeleton-panel .route-skeleton-line { animation-delay: 0.2s; }
@keyframes route-skeleton-pulse { 50% { opacity: 0.35; } }
`;

/** Styled pending state for every lazy route chunk. */
function RouteSkeleton() {
  return (
    <div className="route-skeleton" role="status" aria-busy="true">
      <span className="visually-hidden">Loading page…</span>
      <div className="route-skeleton-line route-skeleton-title" aria-hidden="true" />
      <div className="route-skeleton-line" style={{ width: "58%" }} aria-hidden="true" />
      <div className="route-skeleton-line" style={{ width: "41%" }} aria-hidden="true" />
      <div className="route-skeleton-panel" aria-hidden="true">
        <div className="route-skeleton-line" style={{ width: "86%" }} />
        <div className="route-skeleton-line" style={{ width: "64%" }} />
      </div>
    </div>
  );
}

/** 404 with noindex — keeps the page component itself meta-free. */
function NotFoundRoute() {
  usePageMeta({
    title: "Page not found",
    description: "The page you asked for does not exist.",
    noindex: true,
  });
  return <NotFound />;
}

export function App() {
  const location = useLocation();
  const isDemo = location.pathname.startsWith("/demos/");
  return (
    <>
      <style>{SHELL_CSS}</style>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <RouteAnnouncer />
      <Nav />
      <main id="main" tabIndex={-1} className="app-main app-main--fluid">
        <Suspense fallback={<RouteSkeleton />}>
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
            <Route path="/services" element={<Services />} />
            <Route path="/contact" element={<Contact />} />
            <Route path="/glossary" element={<Glossary />} />
            <Route path="/about" element={<Navigate to="/services" replace />} />
            <Route path="*" element={<NotFoundRoute />} />
          </Routes>
        </Suspense>
      </main>
      {!isDemo && <Footer />}
    </>
  );
}
