<!-- Deliberate fixture SFC for the compat matrix (Svelte stack).
     The engine scans .svelte files directly (v0.4.2 added the extension to
     the scanner), so the style block below carries a real, detected RTL002
     defect: physical padding inside the SFC. The logical twin must stay
     silent. A global stylesheet pair (src/app.css, src/main.js) ships next
     to the component the way real Svelte projects do. -->
<script>
  export let items = [];
</script>

<main class="panel">
  <h2 class="panel-title">سبد خرید شما</h2>
  <p>مجموع اقلام با ارسال سریع به خانه شما می‌رسد</p>
  <!-- defect: physical padding in the SFC style block -->
  <div class="panel-body">
    <span class="price">۱۲۰</span>
    <span class="price-note">اقلام انتخاب‌شده</span>
  </div>
  <!-- correct: logical twin -->
  <div class="panel-body-ok">سبد خالی</div>
</main>

<style>
/* defect block — RTL002: physical padding inside the SFC style block */
.panel {
  padding-right: 16px;
}

/* correct block — logical twin, must stay silent */
.panel-ok {
  padding-inline-end: 16px;
}
</style>
