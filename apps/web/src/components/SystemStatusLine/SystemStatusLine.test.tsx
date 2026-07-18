import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SystemStatusLine } from "./SystemStatusLine";

describe("SystemStatusLine", () => {
  it("renders label when visible", () => {
    render(<SystemStatusLine label="Checking your request…" visible />);
    expect(screen.getByRole("status").textContent).toContain("Checking your request…");
  });

  it("renders nothing when hidden", () => {
    const { container } = render(<SystemStatusLine label="Hidden" visible={false} />);
    expect(container.firstChild).toBeNull();
  });
});
