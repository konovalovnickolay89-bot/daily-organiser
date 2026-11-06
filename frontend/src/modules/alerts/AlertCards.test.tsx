import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AlertCards } from "./AlertCards";

const listAlerts = vi.fn();
const dismissAlert = vi.fn();

vi.mock("../../api/alerts", () => ({
  listAlerts: () => listAlerts(),
  dismissAlert: (kind: string) => dismissAlert(kind),
}));

const failing = {
  kind: "mistral_failing",
  title: "Assistant failing",
  detail: "Mistral failed 3 or more times in 15 minutes. Nothing was sent.",
};

const database = {
  kind: "database_error",
  title: "Database error",
  detail: "The house database reported an error. Nothing was sent.",
};

describe("Alert cards", () => {
  beforeEach(() => {
    cleanup();
    listAlerts.mockReset();
    dismissAlert.mockReset();
  });

  it("shows one card per kind and dismisses that incident", async () => {
    listAlerts.mockResolvedValue({ items: [failing, database] });
    dismissAlert.mockResolvedValue({ items: [database] });
    render(<AlertCards />);
    expect(await screen.findByRole("heading", { name: "Assistant failing" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Database error" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss Assistant failing" }));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Assistant failing" })).toBeNull());
    expect(screen.getByRole("heading", { name: "Database error" })).toBeTruthy();
    expect(dismissAlert).toHaveBeenCalledWith("mistral_failing");
  });

  it("renders nothing when there are no alerts", async () => {
    listAlerts.mockResolvedValue({ items: [] });
    const { container } = render(<AlertCards />);
    await waitFor(() => expect(listAlerts).toHaveBeenCalled());
    expect(container.querySelector("[data-module='alerts']")).toBeNull();
  });
});
