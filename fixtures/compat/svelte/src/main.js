// Deliberate fixture entry point for the compat matrix (Svelte stack).
// Mounts the App component the classic Svelte 4 way and loads the
// global stylesheet. The component file itself carries the deliberate
// defect pair, but the engine's extension set does not cover .svelte
// files, so the scannable defect pair for the matrix lives in app.css.
import "./app.css";
import App from "./App.svelte";

const target = document.getElementById("app");

export default new App({ target });
