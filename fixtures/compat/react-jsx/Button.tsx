// Deliberate fixture: React button for the compat matrix.
// Defect actually caught: the kebab-case physical declaration inside the
// CSS-in-JS template literal (RTL001) — the engine's CSS scanner is lexical
// and reads template literals like stylesheets.
// Honest limitation, documented in the matrix: the camelCase style object
// (marginLeft: 8) is NOT detected by the current engine, because the scanner
// matches kebab-case property names only. A dedicated JSX style-object rule
// is future work; until then this gap is reported, not hidden.
const cardCss = `
  .btn-card {
    margin-left: 8px;
  }
`;

export default function Button() {
  const warnStyle = { marginLeft: 8 };
  return (
    <>
      <button className="btn-card" style={warnStyle}>
        افزودن به سبد
      </button>
      {/* correct counterpart: logical inline object — must stay silent */}
      <button className="btn-ok" style={{ marginInlineStart: 8 }}>
        حذف از سبد
      </button>
    </>
  );
}
