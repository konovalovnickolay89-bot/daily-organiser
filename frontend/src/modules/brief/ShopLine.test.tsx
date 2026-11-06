import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { ShopLine } from "./ShopLine";

function Harness() {
  const [ticked, setTicked] = useState(false);
  return <ShopLine name="Oat milk" ticked={ticked} onToggle={() => setTicked((value) => !value)} />;
}

describe("ShopLine", () => {
  it("ticks and unticks a name", () => {
    render(<Harness />);
    const box = screen.getByRole("checkbox", { name: "Oat milk" });
    expect((box as HTMLInputElement).checked).toBe(false);
    fireEvent.click(box);
    expect((box as HTMLInputElement).checked).toBe(true);
    fireEvent.click(box);
    expect((box as HTMLInputElement).checked).toBe(false);
  });
});
