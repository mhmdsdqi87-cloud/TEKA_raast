// Deliberate fixture entry point for the compat matrix (Vite vanilla).
// Wires the stylesheet into the page; all defects live in style.css.
import "./style.css";

document.querySelector(".gallery-actions").classList.add("is-ready");
