import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

// jsdom has no layout engine: the chat scrolls its transcript into view on
// every message, which would throw without this stub.
Element.prototype.scrollIntoView = vi.fn();

// Dashboard.css media queries are inert here, but any code that asks whether a
// breakpoint matches still needs an object to call.
if (!window.matchMedia) {
  window.matchMedia = () => ({
    matches: false,
    media: "",
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false
  });
}
