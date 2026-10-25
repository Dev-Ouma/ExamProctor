import { render, screen } from "@testing-library/react";
import { App } from "../src/App";

describe("App", () => {
  it("shows the staging banner in staging mode", () => {
    render(<App mode="staging" />);
    expect(screen.getByRole("status").textContent).toContain("Staging");
  });

  it("hides the staging banner in live mode", () => {
    render(<App mode="live" />);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
