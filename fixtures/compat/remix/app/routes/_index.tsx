// Deliberate fixture route for the compat matrix (Remix stack).
// The engine scans the route module as source text: the inline
// critical-CSS template literal is read lexically like a stylesheet.
// The defect is the physical text alignment in that literal (RTL004) —
// it pins the inline axis and does not flip under dir="rtl" — while the
// logical twin in the same literal must stay silent. Persian copy in
// the JSX arms the evidence gate. The compiler, loaders and runtime
// styling are not modeled.
const criticalCss = `
  .cart-cta {
    text-align: left;
  }

  .cart-cta-ok {
    text-align: start;
  }
`;

export default function Index() {
  return (
    <main>
      <style>{criticalCss}</style>
      <h1>فروشگاه نور</h1>
      {/* defect: physical alignment in the inline style block (RTL004) */}
      <button className="cart-cta">افزودن به سبد</button>
      {/* correct: logical twin, must stay silent */}
      <button className="cart-cta-ok">جستجوی محصولات</button>
    </main>
  );
}
