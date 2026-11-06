import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FeatureSettings } from "./FeatureSettings";

const getFeatureSettings = vi.fn();
const patchFeatureSettings = vi.fn();
const refresh = vi.fn();

vi.mock("../../api/system", () => ({
  getFeatureSettings: () => getFeatureSettings(),
  patchFeatureSettings: (body: unknown) => patchFeatureSettings(body),
}));

vi.mock("../../house/HouseContext", () => ({
  useHouse: () => ({ refresh }),
}));

const settings = {
  playlist: {
    enabled: false,
    available: true,
    source: "hearthis",
    profile: "chlorophil",
    detail: "The playlist line is off.",
  },
  alerts: { enabled: true },
  webhooks: { enabled: true, banto: "configured", banto_x: "not configured" },
  voice: {
    mic: "off" as const,
    env_enabled: false,
    voxtral: "off",
    detail: "The microphone stays off until voice input is turned on.",
  },
  x: {
    enabled: false,
    sync_minutes: 30,
    daily_cap: 40,
    from_max: 10,
    draft_expiry_days: 7,
    detail: "X stays off until X_ENABLED is set. These limits are saved for when it is on.",
  },
  agent_context: { token_budget: 2000, memory_limit: 10, smart_add_days: 3, catch_up_days: 7 },
  docs: { state: "off", detail: "Docs are off." },
};

describe("Feature settings", () => {
  beforeEach(() => {
    cleanup();
    getFeatureSettings.mockReset();
    patchFeatureSettings.mockReset();
    refresh.mockReset();
    getFeatureSettings.mockResolvedValue(settings);
  });

  it("shows playlist, alerts, voice, X limits, context, and docs", async () => {
    render(<FeatureSettings />);
    expect(await screen.findByRole("heading", { name: "Playlist" })).toBeTruthy();
    expect(screen.getByText("hearthis")).toBeTruthy();
    expect(screen.getByText("chlorophil")).toBeTruthy();
    expect(screen.getByText("The playlist line is off.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Alerts and webhooks" })).toBeTruthy();
    expect(screen.getByText("configured")).toBeTruthy();
    expect(screen.getByText("not configured")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Voice" })).toBeTruthy();
    expect(screen.getByText("The microphone stays off until voice input is turned on.")).toBeTruthy();
    expect((screen.getByRole("switch", { name: "Microphone" }) as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByRole("heading", { name: "X limits" })).toBeTruthy();
    expect(screen.getByLabelText("Sync interval in minutes")).toBeTruthy();
    expect(screen.getByLabelText("Daily cap")).toBeTruthy();
    expect(screen.getByLabelText("From X maximum")).toBeTruthy();
    expect(screen.getByLabelText("Draft expiry in days")).toBeTruthy();
    expect(screen.getByText(/X stays off until X_ENABLED is set/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Agent context" })).toBeTruthy();
    expect(screen.getByLabelText("Context token budget")).toBeTruthy();
    expect(screen.getByLabelText("Memory lines")).toBeTruthy();
    expect(screen.getByLabelText("Smart Add days")).toBeTruthy();
    expect(screen.getByLabelText("Catch-up days")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Docs" })).toBeTruthy();
    expect(screen.getByText("Docs are off.")).toBeTruthy();
  });

  it("saves each switch and the X limits without an enable flag", async () => {
    patchFeatureSettings.mockImplementation(async (body: Record<string, boolean | number>) => {
      if ("playlist_enabled" in body) return { ...settings, playlist: { ...settings.playlist, enabled: true, detail: "" } };
      if ("alerts_enabled" in body) return { ...settings, alerts: { enabled: false } };
      if ("x_sync_minutes" in body) return { ...settings, x: { ...settings.x, sync_minutes: body.x_sync_minutes } };
      return settings;
    });
    render(<FeatureSettings />);
    await screen.findByRole("switch", { name: "Playlist" });

    fireEvent.click(screen.getByRole("switch", { name: "Playlist" }));
    await waitFor(() => expect(patchFeatureSettings).toHaveBeenCalledWith({ playlist_enabled: true }));
    expect(refresh).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("switch", { name: "Alerts" }));
    await waitFor(() => expect(patchFeatureSettings).toHaveBeenCalledWith({ alerts_enabled: false }));

    fireEvent.click(screen.getByRole("switch", { name: "Webhooks" }));
    await waitFor(() => expect(patchFeatureSettings).toHaveBeenCalledWith({ webhooks_enabled: false }));

    fireEvent.change(screen.getByLabelText("Sync interval in minutes"), { target: { value: "15" } });
    fireEvent.click(screen.getByRole("button", { name: "Save X limits" }));
    await waitFor(() =>
      expect(patchFeatureSettings).toHaveBeenCalledWith({
        x_sync_minutes: 15,
        x_daily_cap: 40,
        x_from_max: 10,
        x_draft_expiry_days: 7,
      }),
    );
    const sent = JSON.stringify(patchFeatureSettings.mock.calls);
    expect(sent).not.toContain("x_enabled");
    expect(sent).not.toContain("secret");
  });
});
