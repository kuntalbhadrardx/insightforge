import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Uploader from "../components/Uploader.jsx";

vi.mock("../api", () => ({
  uploadFile: vi.fn(async () => ({ document_id: "doc-1", total_pages: 1 }))
}));

/** One megabyte of bytes, so the size checks have something real to measure. */
function bytes(size) {
  return new Uint8Array(size);
}

function renderUploader() {
  const { container } = render(
    <Uploader
      endpoint="/upload/paper"
      token="test-token"
      accept=".pdf"
      title="Upload a research paper"
      maxSizeMB={1}
    />
  );
  return container.querySelector('input[type="file"]');
}

/**
 * Deliver a file to the hidden input the way a drop would: past the native
 * `accept` filter, so the component's own validation is what gets tested.
 */
function chooseFile(input, file) {
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  fireEvent.change(input, { target: { files: [file] } });
}

describe("Uploader rejections", () => {
  it("rejects a .txt file and names the supported format", async () => {
    const input = renderUploader();
    chooseFile(input, new File(["notes"], "notes.txt", { type: "text/plain" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "notes.txt is not .pdf"
    );
  });

  it("rejects an empty file and says it has no bytes", async () => {
    const input = renderUploader();
    chooseFile(input, new File([], "empty.pdf", { type: "application/pdf" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "empty.pdf is empty (0 bytes)."
    );
  });

  it("rejects an oversize file and quotes its size against the limit", async () => {
    const input = renderUploader();
    chooseFile(
      input,
      new File([bytes(1024 * 1024 + 1)], "big.pdf", { type: "application/pdf" })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "big.pdf is 1.0 MB; the limit is 1 MB."
    );
  });
});
