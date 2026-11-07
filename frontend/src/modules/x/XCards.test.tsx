import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { XCards } from "./XCards";

const listXItems = vi.fn();
const pollX = vi.fn();
const applyXItem = vi.fn();
const dismissXItem = vi.fn();
const postXDraft = vi.fn();

vi.mock("../../api/x", () => ({
  listXItems: () => listXItems(),
  pollX: () => pollX(),
  applyXItem: (id: string) => applyXItem(id),
  dismissXItem: (id: string) => dismissXItem(id),
  postXDraft: (id: string) => postXDraft(id),
}));

const bookmark = {
  id: "b1",
  kind: "bookmark" as const,
  summary: "Put the bins out tonight",
  detail: "@housebin",
  url: null,
  expires_at: null,
};

const watch = {
  id: "w1",
  kind: "watch_match" as const,
  summary: "Council collection moved to Friday",
  detail: "@housebin",
  url: null,
  expires_at: null,
};

const draft = {
  id: "d1",
  kind: "draft" as const,
  summary: "The boiler filter is in the hall",
  detail: "Say it once.",
  url: null,
  expires_at: "2099-01-01T00:00:00Z",
};

const expired = {
  id: "d0",
  kind: "draft" as const,
  summary: "This draft expired",
  detail: "Old.",
  url: null,
  expires_at: "2000-01-01T00:00:00Z",
};

describe("X cards", () => {
  beforeEach(() => {
    cleanup();
    listXItems.mockReset();
    pollX.mockReset();
    applyXItem.mockReset();
    dismissXItem.mockReset();
    postXDraft.mockReset();
    pollX.mockResolvedValue({ ran: false, reason: "cached" });
    applyXItem.mockResolvedValue({ id: "b1", status: "applied" });
    dismissXItem.mockResolvedValue({ id: "w1", status: "dismissed" });
    postXDraft.mockResolvedValue({ id: "d1", status: "posted", tweet_id: "9001" });
  });

  it("hides an expired draft and posts only after confirm", async () => {
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function close() {
      this.removeAttribute("open");
    };
    listXItems.mockResolvedValue({ enabled: true, items: [bookmark, watch, draft, expired] });
    render(<XCards />);
    expect(await screen.findByText("Put the bins out tonight")).toBeTruthy();
    expect(screen.getByText("Council collection moved to Friday")).toBeTruthy();
    expect(screen.queryByText("This draft expired")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Keep Put the bins out tonight" }));
    await waitFor(() => expect(applyXItem).toHaveBeenCalledWith("b1"));
    expect(screen.queryByText("Put the bins out tonight")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Not now Council collection moved to Friday" }));
    await waitFor(() => expect(dismissXItem).toHaveBeenCalledWith("w1"));

    fireEvent.click(screen.getByRole("button", { name: "Post The boiler filter is in the hall" }));
    expect(postXDraft).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Post this to X?" })).toBeTruthy();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Post" }));
    await waitFor(() => expect(postXDraft).toHaveBeenCalledWith("d1"));
    expect(await screen.findByText("Posted.")).toBeTruthy();
  });

  it("stays empty while X is off", async () => {
    listXItems.mockResolvedValue({ enabled: false, items: [] });
    const { container } = render(<XCards />);
    await waitFor(() => expect(listXItems).toHaveBeenCalled());
    expect(container.querySelector("[data-module='x-cards']")).toBeNull();
    expect(pollX).not.toHaveBeenCalled();
  });
});
