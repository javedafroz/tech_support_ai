import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThoughtStreamPanel } from "./ThoughtStreamPanel";

describe("ThoughtStreamPanel", () => {
  const thoughts = ["Thinking…", "Checking your request…", "Creating ticket…"];

  it("expands while live and shows all thoughts", () => {
    render(<ThoughtStreamPanel thoughts={thoughts} isLive />);
    expect(screen.getByText("Thinking…")).toBeTruthy();
    expect(screen.getByText("Creating ticket…")).toBeTruthy();
  });

  it("auto-collapses when streaming completes", () => {
    const { rerender } = render(<ThoughtStreamPanel thoughts={thoughts} isLive />);
    expect(screen.getByText("Thinking…")).toBeTruthy();

    rerender(<ThoughtStreamPanel thoughts={thoughts} isLive={false} />);
    expect(screen.queryByText("Thinking…")).toBeNull();
    expect(screen.getByText(/3 steps/i)).toBeTruthy();
  });

  it("can be expanded manually after collapse", () => {
    render(<ThoughtStreamPanel thoughts={thoughts} />);

    fireEvent.click(screen.getByRole("button", { name: /expand processing steps/i }));
    expect(screen.getByText("Thinking…")).toBeTruthy();
  });
});
