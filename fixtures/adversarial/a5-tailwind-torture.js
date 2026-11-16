// A5 — Tailwind torture: arbitrary values, negative utilities, stacked
// variants, tokens inside prose words, responsive prefixes, RTL variants.
const cls = {
  spacing: "ml-2 mr-[3px] -ml-1 pl-4 pr-0.5 px-2 ms-1 me-2 ps-3 pe-4",
  align: "text-left text-right text-start text-end",
  inset: "left-0 right-2 start-0 end-4",
  border: "border-l-2 border-r-4 border-s-2 border-e-4",
  radius: "rounded-l-lg rounded-r-full rounded-s-lg rounded-e-full",
  translate: "translate-x-4 -translate-x-2 rtl:-translate-x-4",
  wordlike: "right-to-left left-aligned ml-kitchen-sink-not-a-utility",
  responsive: "sm:ml-2 md:text-left lg:pl-3 xl:mr-4",
};
