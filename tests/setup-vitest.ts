import "@testing-library/jest-dom/vitest";

class EventSourceMock {
  addEventListener() {}
  removeEventListener() {}
  close() {}
}

Object.defineProperty(globalThis, "EventSource", {
  configurable: true,
  writable: true,
  value: EventSourceMock,
});
