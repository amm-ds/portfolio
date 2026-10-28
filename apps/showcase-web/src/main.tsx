import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
// JetBrains Mono at 400 (body mono) + 700 (bold) only; fontsource CSS already
// declares font-display: swap. The 400 file is preloaded below so first paint
// doesn't wait on the CSS-discovered font request.
import jetbrainsMono400 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/700.css";
import { App } from "./App";
import { TopLevelErrorBoundary } from "./components/TopLevelErrorBoundary";
import "./styles.css";

const fontPreload = document.createElement("link");
fontPreload.rel = "preload";
fontPreload.href = jetbrainsMono400;
fontPreload.as = "font";
fontPreload.type = "font/woff2";
fontPreload.crossOrigin = "anonymous";
document.head.appendChild(fontPreload);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TopLevelErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </TopLevelErrorBoundary>
  </React.StrictMode>,
);
