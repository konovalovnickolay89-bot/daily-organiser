import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryScreen } from "./MemoryScreen";

const listMemory = vi.fn();
const searchMemory = vi.fn();
const pinMemory = vi.fn();
const forgetMemory = vi.fn();
const exportMemory = vi.fn();

vi.mock("../../api/memory", () => ({
  listMemory: (...args: unknown[]) => listMemory(...args),
  searchMemory: (...args: unknown[]) => searchMemory(...args),
  pinMemory: (...args: unknown[]) => pinMemory(...args),
  forgetMemory: (...args: unknown[]) => forgetMemory(...args),
  exportMemory: (...args: unknown[]) => exportMemory(...args),
}));

const milk = {
  id: "m1",
  kind: "fact",
  text: "The milk stays in the door",
  source: "remember",
  created_at: "2026-11-06T08:00:00Z",
  last_used_at: null,
  pinned: false,
};

describe("Memory screen", () => {
  beforeEach(() => {
    cleanup();
    listMemory.mockReset();
    searchMemory.mockReset();
    pinMemory.mockReset();
    forgetMemory.mockReset();
    exportMemory.mockReset();
    listMemory.mockResolvedValue({ items: [milk] });
    searchMemory.mockResolvedValue({ mode: "fts", items: [milk] });
  });

  it("lists, searches, pins, and forgets only after confirm", async () => {
    pinMemory.mockResolvedValue({ ...milk, pinned: true });
    forgetMemory.mockResolvedValue({ forgotten: true });
    render(<MemoryScreen />);
    expect(await screen.findByText("The milk stays in the door")).toBeTruthy();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search memory" }), { target: { value: "milk" } });
    await waitFor(() => expect(searchMemory).toHaveBeenCalledWith("milk"));
    expect(await screen.findByText("Matched on words.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Pin" }));
    await waitFor(() => expect(pinMemory).toHaveBeenCalledWith("m1", true));
    expect(screen.getByRole("button", { name: "Unpin" }).getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "Forget" }));
    expect(forgetMemory).not.toHaveBeenCalled();
    expect(screen.getByText("Forget this memory? It is removed from the house.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Forget" }));
    await waitFor(() => expect(forgetMemory).toHaveBeenCalledWith("m1"));
    await waitFor(() => expect(screen.queryByText("The milk stays in the door")).toBeNull());
  });

  it("exports JSON from the button", async () => {
    exportMemory.mockResolvedValue({ exported_at: "2026-11-06T08:00:00Z", items: [milk] });
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: () => "blob:memory",
      revokeObjectURL: () => undefined,
    });
    const click = vi.fn();
    const real = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const node = real(tag);
      if (tag === "a") node.click = click;
      return node;
    });
    render(<MemoryScreen />);
    await screen.findByText("The milk stays in the door");
    fireEvent.click(screen.getByRole("button", { name: "Export memory" }));
    await waitFor(() => expect(exportMemory).toHaveBeenCalled());
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(JSON.stringify(exportMemory.mock.calls)).not.toContain("embedding");
  });

  it("shows an empty state when nothing matches", async () => {
    searchMemory.mockResolvedValue({ mode: "fts", items: [] });
    render(<MemoryScreen />);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search memory" }), { target: { value: "no-such-memory" } });
    expect(await screen.findByText("Nothing matches.")).toBeTruthy();
  });
});
