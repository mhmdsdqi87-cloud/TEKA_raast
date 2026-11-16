// Deliberate fixture: React button for the compat matrix.
// Both spellings the engine covers are present:
//   1. the kebab-case declaration inside the CSS-in-JS template literal —
//      the lexical CSS scanner reads template literals like stylesheets.
//   2. the camelCase style object below — property names are normalized to
//      kebab-case before matching, so style objects fire the same rule;
//      the suggested fix stays camelCase (marginInlineStart).
// Correct counterparts use logical inline properties and must stay silent.
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
