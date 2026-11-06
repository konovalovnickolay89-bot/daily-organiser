import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QuietSuggestion } from "./QuietSuggestion";

const getPlaylist = vi.fn();

vi.mock("../../api/playlist", () => ({
  getPlaylist: () => getPlaylist(),
}));

const track = {
  shown: true,
  offline: false,
  title: "Morning Haze",
  genre: "Dub",
  artwork_url: "https://img.hearthis.at/art/thumb.jpg",
  permalink_url: "https://hearthis.at/chlorophil/morning-haze/",
};

describe("QuietSuggestion", () => {
  beforeEach(() => {
    cleanup();
    getPlaylist.mockReset();
  });

  it("stays hidden until a source is set", async () => {
    getPlaylist.mockResolvedValue({ shown: false, offline: false, title: null, genre: null, artwork_url: null, permalink_url: null });
    render(<QuietSuggestion />);
    await waitFor(() => expect(getPlaylist).toHaveBeenCalled());
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows the latest track as a link and does not embed a player", async () => {
    getPlaylist.mockResolvedValue(track);
    render(<QuietSuggestion />);
    const link = await screen.findByRole("link", { name: /Morning Haze/ });
    expect(link.getAttribute("href")).toBe(track.permalink_url);
    expect(link.getAttribute("target")).toBe("_blank");
    expect(screen.getByText("Dub")).toBeTruthy();
    expect(document.querySelector("audio, video")).toBeNull();
    expect(link.className).toContain("min-h-11");
  });

  it("stays quiet when the source is offline", async () => {
    getPlaylist.mockResolvedValue({ ...track, offline: true, title: null, permalink_url: null, artwork_url: null, genre: null });
    render(<QuietSuggestion />);
    expect(await screen.findByText("The playlist is quiet right now.")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
