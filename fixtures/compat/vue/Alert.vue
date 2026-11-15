<!-- Deliberate fixture: Vue single-file component for the compat matrix.
     The engine scans SFC style blocks like plain CSS; template directives
     are not parsed. The defect is the physical padding declaration in the
     style block (RTL002); the logical twin in the second rule must stay
     silent. Persian copy in the template arms the evidence gate. -->
<template>
  <div class="alert" role="alert">
    <strong>هشدار سیستم</strong>
    <p>فضای داخلی هشدار با ویژگی فیزیکی تنظیم شده است</p>
  </div>
</template>

<style scoped>
/* defect block — RTL002 */
.alert {
  padding-left: 1rem;
}

/* correct block — logical twin, must stay silent */
.alert-ok {
  padding-inline-start: 1rem;
  text-align: start;
}
</style>
