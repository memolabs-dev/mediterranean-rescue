// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithI18n } from "../test/render";
import { MapPeek } from "./MapPeek";
import { MiniMap, MiniMapDefinitions } from "./MiniMap";

function render(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderWithI18n(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("map on a phone", () => {
  it("a tapped point is previewed, and the record opens only on demand", async () => {
    const onOpen = vi.fn();
    const onClose = vi.fn();
    render(
      <MapPeek
        id="00000000-0000-0000-0000-0000000000d1"
        preview
        known={{ date: "2024-02-03", kind: "rescue", people: 42, port: "Port fictif" }}
        onOpen={onOpen}
        onClose={onClose}
      />,
    );
    const peek = screen.getByRole("region", { name: "Event picked on the map" });
    expect(peek.textContent).toContain("Feb 3, 2024");
    expect(peek.textContent).toContain("Port fictif");
    await userEvent.click(screen.getByRole("button", { name: "Close the preview" }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(onOpen).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Open the record/ }));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("shares one coastline path across 25 accessible locators", () => {
    render(
      <>
        <MiniMapDefinitions />
        {Array.from({ length: 25 }, (_, i) => (
          <MiniMap
            key={i}
            position={{ longitude: 12 + i * 0.1, latitude: 34.5 }}
            label={"Locator " + (i + 1)}
          />
        ))}
      </>,
    );
    expect(document.querySelectorAll("path#med-rescue-mini-land")).toHaveLength(1);
    expect(document.querySelectorAll('use[href="#med-rescue-mini-land"]')).toHaveLength(25);
    expect(screen.getAllByRole("img")).toHaveLength(25);
    expect(screen.getByRole("img", { name: "Locator 1" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Locator 25" })).toBeTruthy();
  });

  it("a locator without a position says so instead of showing an empty map", () => {
    render(<MiniMap position={null} label="Position unknown" unknownLabel="Position unknown" />);
    expect(screen.getByText("Position unknown")).toBeTruthy();
  });
});
