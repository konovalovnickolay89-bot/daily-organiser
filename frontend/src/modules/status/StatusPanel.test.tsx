import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StatusPanel } from "./StatusPanel";

const getStatus = vi.fn();

vi.mock("../../api/system", () => ({
  getStatus: () => getStatus(),
}));

describe("Status panel", () => {
  beforeEach(() => {
    cleanup();
    getStatus.mockReset();
  });

  it("shows health, version, the last success, the last poll, and the database size", async () => {
    getStatus.mockResolvedValue({
      health: "ok",
      version: "0.3.0",
      last_mistral_success: "2026-11-06T08:05:00+00:00",
      last_activity_poll: null,
      database_bytes: 2 * 1024 * 1024,
    });
    render(<StatusPanel />);
    expect(await screen.findByRole("heading", { name: "Status" })).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Ok")).toBeTruthy());
    expect(screen.getByText("0.3.0")).toBeTruthy();
    expect(screen.getByText("6 Nov, 08:05")).toBeTruthy();
    expect(screen.getByText("Not yet")).toBeTruthy();
    expect(screen.getByText("2.0 MB")).toBeTruthy();
  });

  it("names Mistral, Voxtral, Google, TfL, X, and hearthis", async () => {
    getStatus.mockResolvedValue({
      health: "ok",
      version: "0.5.0",
      last_mistral_success: null,
      last_activity_poll: null,
      database_bytes: 1024,
      services: [
        { name: "mistral", state: "not configured", detail: "No assistant key." },
        { name: "voxtral", state: "unavailable", detail: "Voxtral is unavailable until the assistant key is set." },
        { name: "google", state: "ok", detail: "A read succeeded." },
        { name: "tfl", state: "attention", detail: "The last journey check failed." },
        { name: "x", state: "off", detail: "X is off." },
        { name: "hearthis", state: "unknown", detail: "Not read yet." },
      ],
    });
    render(<StatusPanel />);
    expect(await screen.findByText("Mistral")).toBeTruthy();
    expect(screen.getByText("Voxtral")).toBeTruthy();
    expect(screen.getByText("Google")).toBeTruthy();
    expect(screen.getByText("TfL")).toBeTruthy();
    expect(screen.getByText("hearthis")).toBeTruthy();
    expect(screen.getByText("Unavailable")).toBeTruthy();
    expect(screen.getByText("Attention")).toBeTruthy();
    expect(screen.getByText("Not configured")).toBeTruthy();
  });
});
