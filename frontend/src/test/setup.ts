import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement scrollIntoView (used by ChatWindow's auto-scroll).
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// jsdom doesn't implement matchMedia; useTheme() needs it to detect the
// system color scheme preference.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}

