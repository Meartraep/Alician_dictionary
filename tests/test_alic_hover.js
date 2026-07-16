const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function loadHoverCode(options = {}) {
  const textNode = { nodeType: 3, nodeValue: options.text || "alpha beta" };
  const renderedRects = options.rects || [{ left: 10, right: 50, top: 10, bottom: 30, width: 40, height: 20 }];
  const createdRanges = [];
  const document = {
    caretRangeFromPoint() {
      return { startContainer: textNode, startOffset: options.offset ?? 2 };
    },
    createRange() {
      const range = {
        startContainer: null,
        startOffset: 0,
        endContainer: null,
        endOffset: 0,
        setStart(node, offset) { this.startContainer = node; this.startOffset = offset; },
        setEnd(node, offset) { this.endContainer = node; this.endOffset = offset; },
        getClientRects() { return renderedRects; },
      };
      createdRanges.push(range);
      return range;
    },
  };
  const context = {
    console,
    document,
    Node: { TEXT_NODE: 3, ELEMENT_NODE: 1 },
    state: { settings: { alicHoverDelay: options.delay ?? 300 } },
    window: {},
    setTimeout,
    clearTimeout,
  };
  vm.createContext(context);
  const source = fs.readFileSync(path.join(__dirname, "..", "webui", "js", "utils.js"), "utf8");
  vm.runInContext(source, context, { filename: "utils.js" });
  return { context, textNode, createdRanges };
}

test("returns only the exact word under the pointer", () => {
  const { context, textNode } = loadHoverCode();
  const result = context._alicGetWordRangeAtPoint({ contains: node => node === textNode }, 20, 20);
  assert.equal(result.word, "alpha");
  assert.equal(result.start, 0);
  assert.equal(result.end, 5);
});

test("rejects caret snapping when pointer is outside the word rectangle", () => {
  const { context, textNode } = loadHoverCode({ offset: 5 });
  const result = context._alicGetWordRangeAtPoint({ contains: node => node === textNode }, 70, 20);
  assert.equal(result, null);
});

test("rejects a caret text node outside the registered hover root", () => {
  const { context } = loadHoverCode();
  const result = context._alicGetWordRangeAtPoint({ contains: () => false }, 20, 20);
  assert.equal(result, null);
});

test("same spelling at different DOM positions is not the same hover target", () => {
  const { context } = loadHoverCode({ text: "same same" });
  const first = { node: { nodeValue: "same" }, start: 0, end: 4 };
  const second = { node: { nodeValue: "same" }, start: 0, end: 4 };
  assert.equal(context._alicSameWordRange(first, second), false);
  assert.equal(context._alicSameWordRange(first, first), true);
});

test("zero millisecond hover delay remains zero", () => {
  const { context } = loadHoverCode({ delay: 0 });
  assert.equal(context._alicHoverDelay(), 0);

  context.els = {};
  context.document.body = { classList: { toggle() {} } };
  const writingSource = fs.readFileSync(path.join(__dirname, "..", "webui", "js", "writing.js"), "utf8");
  vm.runInContext(writingSource, context, { filename: "writing.js" });
  context.applyAppSettings({ alic_hover_delay: 0 });
  assert.equal(context.state.settings.alicHoverDelay, 0);
});
