import React from "react";
import ReactDOM from "react-dom/client";
import OverlayApp from "./Overlay";
import "./style.css";

const OHIF = new URLSearchParams(location.search).get("ohif")
  || "http://localhost:8042/app/explorer.html";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <OverlayApp ohifUrl={OHIF} />
  </React.StrictMode>
);
