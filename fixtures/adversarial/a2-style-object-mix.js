/* A2 — CSS-in-JS spellings that historically diverged between detection and
   normalization (camelCase, vendor prefixes, quoting styles, abutting
   punctuation, trailing commas, single-line multi-declarations). */
const styles = {
  card: {
    marginLeft: '4px',
    marginRight: 8,
    paddingLeft: "1rem",
    paddingRight: '2px',
    textAlign: 'left',
    letterSpacing: '0.5px',
    WebkitTransition: 'all 0.2s',
    msTransform: 'translateX(4px)',
    marginInlineStart: '2px',
  },
  odd: {paddingLeft:'3px',textAlign:'right',},
  safe: { marginInlineEnd: '1px', textAlign: 'start', letterSpacing: 0 },
};
