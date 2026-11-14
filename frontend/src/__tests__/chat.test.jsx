import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App.jsx";
import * as api from "../api";

vi.mock("../api", () => ({
  BASE_URL: "http://api.test",
  checkBackend: vi.fn(async () => true),
  fetchDocuments: vi.fn(),
  fetchChatHistory: vi.fn(),
  fetchReports: vi.fn(),
  sendQuery: vi.fn(),
  deleteChatHistory: vi.fn(),
  downloadReport: vi.fn(),
  runAnomalies: vi.fn()
}));

// The console mounts behind a Supabase session, so the fake session is the way
// in. Nothing here touches the network.
vi.mock("../supabase", () => {
  const session = {
    access_token: "test-token",
    user: { email: "researcher@example.com" }
  };
  return {
    supabase: {
      auth: {
        getSession: vi.fn(async () => ({ data: { session } })),
        onAuthStateChange: vi.fn(() => ({
          data: { subscription: { unsubscribe: vi.fn() } }
        })),
        signOut: vi.fn(async () => ({}))
      }
    }
  };
});

const DOCUMENTS = [
  { id: "doc-1", filename: "attention.pdf", total_pages: 9, chunk_count: 12 },
  { id: "doc-2", filename: "detector.pdf", total_pages: 6, chunk_count: 8 }
];

/** Render the console and land on the chat view with a paper selected. */
async function openChat() {
  render(<App />);
  const user = userEvent.setup();
  // The sidebar entry comes first in the DOM; the overview's quick action
  // shares the same name, so take the nav one.
  const [navEntry] = await screen.findAllByRole("button", { name: "Research Chat" });
  await user.click(navEntry);
  const box = await screen.findByPlaceholderText(/Ask about methods/);
  await waitFor(() => expect(box).toBeEnabled());
  return { user, box };
}

beforeEach(() => {
  api.fetchDocuments.mockResolvedValue(DOCUMENTS);
  api.fetchChatHistory.mockResolvedValue({ messages: [] });
  api.fetchReports.mockResolvedValue([]);
  api.sendQuery.mockReset();
});

describe("sending a question", () => {
  it("restores the question into the box and says where it went when the send fails", async () => {
    const { user, box } = await openChat();
    api.sendQuery.mockRejectedValueOnce(new Error("Inference failed"));

    const question = "What contamination threshold did the authors use?";
    await user.type(box, question);
    await user.click(screen.getByRole("button", { name: "Send question" }));

    expect(
      await screen.findByText(/Inference failed — your question is back in the box\./)
    ).toBeInTheDocument();
    expect(box).toHaveValue(question);
  });

  it("does not file an in-flight answer under the paper you switch to", async () => {
    const { user, box } = await openChat();

    let resolveSend;
    api.sendQuery.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSend = resolve;
        })
    );

    await user.type(box, "How many rows were audited?");
    await user.click(screen.getByRole("button", { name: "Send question" }));

    // Switch papers while the request is still open.
    await user.selectOptions(screen.getByLabelText("Paper"), "doc-2");

    await act(async () => {
      resolveSend({ answer: "ANSWER-FOR-DOC-1", citations: [] });
    });

    await waitFor(() =>
      expect(api.fetchChatHistory).toHaveBeenCalledWith("doc-2", "test-token")
    );
    expect(screen.queryByText("ANSWER-FOR-DOC-1")).not.toBeInTheDocument();
  });

  it("makes one request when Enter is pressed twice in a row", async () => {
    const { box } = await openChat();
    api.sendQuery.mockImplementation(() => new Promise(() => {}));

    fireEvent.change(box, { target: { value: "Summarise section 3" } });

    const send = screen.getByRole("button", { name: "Send question" });
    fireEvent.click(send);
    fireEvent.click(send);

    expect(api.sendQuery).toHaveBeenCalledTimes(1);
  });
});
