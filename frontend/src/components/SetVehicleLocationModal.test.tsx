import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { pushVehicleLocation } from "../api/vehicles";
import { renderWithProviders, screen, waitFor } from "../test/render";
import SetVehicleLocationModal from "./SetVehicleLocationModal";

vi.mock("../api/vehicles");

/**
 * Wraps the modal the way a real caller (e.g. VehicleCard) does: `onClose`
 * actually removes it from the DOM, so tests can assert the modal
 * self-closes via its own `onClose()` call rather than just checking that a
 * mock function was invoked.
 */
function SelfClosingHarness({ onSaved }: { onSaved: () => void }) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <SetVehicleLocationModal
      vehicleId="veh-1"
      onClose={() => setOpen(false)}
      onSaved={onSaved}
    />
  );
}

function mockGeolocation(
  impl: (
    success: PositionCallback,
    error?: PositionErrorCallback | null,
  ) => void,
) {
  Object.defineProperty(globalThis.navigator, "geolocation", {
    value: { getCurrentPosition: vi.fn(impl) },
    configurable: true,
  });
}

describe("SetVehicleLocationModal", () => {
  beforeEach(() => {
    vi.mocked(pushVehicleLocation).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
    Reflect.deleteProperty(globalThis.navigator, "geolocation");
  });

  it("autofills the latitude/longitude fields on successful geolocation, leaving them editable", async () => {
    mockGeolocation((success) => {
      success({
        coords: { latitude: 40.4168, longitude: -3.7038 },
      } as GeolocationPosition);
    });
    const user = userEvent.setup();
    renderWithProviders(
      <SetVehicleLocationModal vehicleId="veh-1" onClose={vi.fn()} onSaved={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Use my current location" }));

    expect(screen.getByLabelText("Latitude")).toHaveValue(40.4168);
    expect(screen.getByLabelText("Longitude")).toHaveValue(-3.7038);

    await user.clear(screen.getByLabelText("Latitude"));
    await user.type(screen.getByLabelText("Latitude"), "10");
    expect(screen.getByLabelText("Latitude")).toHaveValue(10);
  });

  it("shows an inline error and leaves fields empty/editable when geolocation is denied", async () => {
    mockGeolocation((_success, error) => {
      error?.({ code: 1, message: "denied" } as GeolocationPositionError);
    });
    const user = userEvent.setup();
    renderWithProviders(
      <SetVehicleLocationModal vehicleId="veh-1" onClose={vi.fn()} onSaved={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Use my current location" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Couldn't get your current location. You can still enter it manually below.",
    );
    expect(screen.getByLabelText("Latitude")).toHaveValue(null);
    expect(screen.getByLabelText("Longitude")).toHaveValue(null);
  });

  it("disables the 'Use my current location' button while the geolocation request is in flight", async () => {
    let resolvePosition: (() => void) | undefined;
    mockGeolocation((success) => {
      resolvePosition = () => {
        success({
          coords: { latitude: 40.4168, longitude: -3.7038 },
        } as GeolocationPosition);
      };
    });
    const user = userEvent.setup();
    renderWithProviders(
      <SetVehicleLocationModal vehicleId="veh-1" onClose={vi.fn()} onSaved={vi.fn()} />,
    );

    const button = screen.getByRole("button", { name: "Use my current location" });
    await user.click(button);

    expect(screen.getByRole("button", { name: "Locating…" })).toBeDisabled();

    resolvePosition?.();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Use my current location" })).toBeEnabled();
    });
  });

  it("submits manually typed values without using geolocation", async () => {
    const onSaved = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <SetVehicleLocationModal vehicleId="veh-1" onClose={vi.fn()} onSaved={onSaved} />,
    );

    await user.type(screen.getByLabelText("Latitude"), "40.1");
    await user.type(screen.getByLabelText("Longitude"), "-3.5");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(pushVehicleLocation).toHaveBeenCalledWith(
        "veh-1",
        expect.objectContaining({ lat: 40.1, lon: -3.5 }),
      );
    });
    expect(onSaved).toHaveBeenCalledWith(
      expect.objectContaining({ latitude: 40.1, longitude: -3.5 }),
    );
  });

  it("blocks submit and shows a validation error for out-of-range coordinates", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <SetVehicleLocationModal vehicleId="veh-1" onClose={vi.fn()} onSaved={vi.fn()} />,
    );

    await user.type(screen.getByLabelText("Latitude"), "999");
    await user.type(screen.getByLabelText("Longitude"), "-3.5");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Latitude must be between -90 and 90, and longitude between -180 and 180.",
    );
    expect(pushVehicleLocation).not.toHaveBeenCalled();
  });

  it("closes the modal on successful save", async () => {
    const onSaved = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<SelfClosingHarness onSaved={onSaved} />);

    await user.type(screen.getByLabelText("Latitude"), "40.1");
    await user.type(screen.getByLabelText("Longitude"), "-3.5");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(onSaved).toHaveBeenCalled();
  });

  it("keeps the modal open with an inline error and the entered values intact when save fails", async () => {
    vi.mocked(pushVehicleLocation).mockRejectedValue(new Error("Too many requests"));
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <SetVehicleLocationModal vehicleId="veh-1" onClose={onClose} onSaved={vi.fn()} />,
    );

    await user.type(screen.getByLabelText("Latitude"), "40.1");
    await user.type(screen.getByLabelText("Longitude"), "-3.5");
    await user.click(screen.getByRole("button", { name: "Save" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Too many requests");
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Latitude")).toHaveValue(40.1);
    expect(screen.getByLabelText("Longitude")).toHaveValue(-3.5);
  });

  it("calls onClose without submitting when Cancel is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <SetVehicleLocationModal vehicleId="veh-1" onClose={onClose} onSaved={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(pushVehicleLocation).not.toHaveBeenCalled();
  });
});
