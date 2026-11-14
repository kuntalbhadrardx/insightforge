import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Dashboard from "../Dashboard.jsx";

const baseProps = {
  documents: [],
  selectedDocId: null,
  onSelectDocument: () => {},
  reports: [],
  online: true,
  onOpenChat: () => {},
  onOpenPaper: () => {},
  onOpenAnomalies: () => {},
  onUpload: () => {},
  onExport: () => {},
  exporting: null
};

describe("Library card error state", () => {
  it("shows the failure, offers Try again and calls the retry", async () => {
    const onRetryDocuments = vi.fn();
    const user = userEvent.setup();

    render(
      <Dashboard
        {...baseProps}
        documentsError="Could not load your library — the API did not answer."
        onRetryDocuments={onRetryDocuments}
      />
    );

    expect(screen.getByText("Library unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("Could not load your library — the API did not answer.")
    ).toBeInTheDocument();

    // The retry must be reachable without scrolling: it sits in the same card.
    const retry = screen.getByRole("button", { name: "Try again" });
    await user.click(retry);

    expect(onRetryDocuments).toHaveBeenCalledTimes(1);
  });
});
