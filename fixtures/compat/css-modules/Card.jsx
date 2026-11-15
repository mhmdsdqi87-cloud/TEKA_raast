// Deliberate fixture: React + CSS Modules card (Arabic content).
// The Arabic labels give the scanner its RTL-script evidence; the JSX file
// itself carries no physical declarations — the defect lives in the module
// and is attributed to Card.module.css.
export default function Card() {
  return (
    <div className="card">
      <h3 className="card__title">بطاقة المنتج</h3>
      <p className="card__body">هذا القسم مبني بالخصائص المنطقية فقط</p>
      <span className="badge">جديد</span>
      <button className="card__actions" type="button">حفظ</button>
    </div>
  );
}
