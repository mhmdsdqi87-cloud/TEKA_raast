// Deliberate fixture: Next.js page (App Router style) for the compat matrix.
// dir="rtl" is set correctly on the wrapper. The defect is the physical
// alignment declaration inside the styled-jsx block — RTL004 fires lexically
// on kebab-case CSS inside <style>. The logical twin in the second rule must
// stay silent. Next.js styled-jsx keeps kebab-case CSS, which is exactly
// what the scanner sees; runtime styling is not evaluated.
export default function Page() {
  return (
    <main dir="rtl">
      <h1>فروشگاه اینترنتی</h1>
      <p>ارسال به سراسر کشور انجام می‌شود</p>
      <style jsx>{`
        .hero {
          text-align: left;
        }
        .hero-ok {
          text-align: start;
        }
      `}</style>
    </main>
  );
}
