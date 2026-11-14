// JS mirror of the accent tokens in index.css. Plotly needs literal colour
// strings, so chart code reads these instead of repeating hex values.
export const ACCENT = "#fdc500";
export const ACCENT_LIGHT = "#ffe680";
export const ON_ACCENT = "#0a0800";

/** The accent at a given alpha, for fills and gridless chart marks. */
export const accentAlpha = (alpha) => `rgba(253, 197, 0, ${alpha})`;
