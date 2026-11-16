<!-- Deliberate fixture root component for the compat matrix (Nuxt 3).
     The engine scans the SFC style block like plain CSS; auto-imports,
     server rendering and compiler output are not parsed. The defect is
     the physical margin declaration in the style block (RTL001); the
     logical twin in the second rule must stay silent. Persian copy in
     the template arms the evidence gate. -->
<template>
  <main class="landing">
    <h1>پیشخوان فروشگاه</h1>
    <!-- defect block: physical margin declaration, RTL001 -->
    <section class="promo">
      <p>تخفیف پایان فصل روی همه محصولات فعال است</p>
      <button class="cta">ذخیره تغییرات</button>
    </section>
    <!-- correct block: logical twin, must stay silent -->
    <section class="promo-ok">
      <p>پشتیبانی پاسخگوی شماست</p>
      <button class="cta-ok">جستجو</button>
    </section>
  </main>
</template>

<style scoped>
/* defect block — RTL001 */
.promo {
  margin-right: 24px;
}

/* correct block — logical twin, must stay silent */
.promo-ok {
  margin-inline-end: 24px;
}
</style>
