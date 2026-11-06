import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QuietSuggestion } from "./QuietSuggestion";

const house = vi.hoisted(() => ({ stub: false }));

vi.mock("../../house/HouseContext", () => ({
  useHouse: () => ({ system: { playlist_stub: house.stub } }),
}));

describe("QuietSuggestion", () => {
  it("stays hidden unless the flag is on", () => {
    house.stub = false;
    const hidden = render(<QuietSuggestion />);
    expect(hidden.queryByText("A playlist is ready, when you want it.")).toBeNull();
    hidden.unmount();
    house.stub = true;
    render(<QuietSuggestion />);
    expect(screen.getByText("A playlist is ready, when you want it.")).toBeTruthy();
  });
});
