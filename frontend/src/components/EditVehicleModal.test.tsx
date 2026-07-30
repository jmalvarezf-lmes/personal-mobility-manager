import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { listCities } from "../api/cities";
import {
  clearSerParkingExemption,
  getSerParkingExemption,
  setSerParkingExemption,
  updateVehicle,
} from "../api/vehicles";
import { fetchZoneOptions } from "../api/zones";
import { renderWithProviders, screen, waitFor } from "../test/render";
import type { VehicleDetail } from "../types/vehicle";
import EditVehicleModal from "./EditVehicleModal";

vi.mock("../api/cities");
vi.mock("../api/vehicles");
vi.mock("../api/zones");

const genericVehicle: VehicleDetail = {
  vehicle_id: "veh-1",
  brand: "generic",
  display_name: "My Car",
  vin: null,
  license_plate: "1234ABC",
  config: { location_token: "tok" },
  ambient_label: null,
};

const toyotaVehicle: VehicleDetail = {
  vehicle_id: "veh-2",
  brand: "toyota",
  display_name: "Toyota Car",
  vin: "VIN123",
  license_plate: null,
  config: { username: "myuser", locale: "en_GB", password: "" },
  ambient_label: null,
};

function mockEmptyExemption() {
  vi.mocked(getSerParkingExemption).mockResolvedValue({ city_code: null, zone_number: null });
  vi.mocked(listCities).mockResolvedValue([
    { code: "madrid", name: "Madrid" },
    { code: "barcelona", name: "Barcelona" },
  ]);
}

describe("EditVehicleModal", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the generic vehicle's fields without Toyota-only fields", async () => {
    mockEmptyExemption();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    expect(screen.getByLabelText("Display Name")).toHaveValue("My Car");
    expect(screen.getByLabelText("License Plate", { exact: false })).toHaveValue("1234ABC");
    expect(screen.queryByLabelText("Username")).not.toBeInTheDocument();
    await waitFor(() => expect(listCities).toHaveBeenCalled());
  });

  it("renders the Toyota vehicle's VIN and prefilled username/locale", async () => {
    mockEmptyExemption();
    renderWithProviders(
      <EditVehicleModal vehicle={toyotaVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    expect(screen.getByText(/VIN: VIN123/)).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toHaveValue("myuser");
    expect(screen.getByLabelText("Locale")).toHaveValue("en_GB");
    expect(screen.getByLabelText("New Password", { exact: false })).toHaveValue("");
    await waitFor(() => expect(listCities).toHaveBeenCalled());
  });

  it("loads the existing exemption's city and zone options on mount", async () => {
    vi.mocked(getSerParkingExemption).mockResolvedValue({
      city_code: "madrid",
      zone_number: "Z1",
    });
    vi.mocked(listCities).mockResolvedValue([{ code: "madrid", name: "Madrid" }]);
    vi.mocked(fetchZoneOptions).mockResolvedValue([
      { zone_number: "Z1", neighbourhood: "Centro" },
    ]);

    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText("City")).toHaveValue("madrid");
    });
    await waitFor(() => {
      expect(screen.getByLabelText("SER Zone")).toHaveValue("Z1");
    });
    expect(fetchZoneOptions).toHaveBeenCalledWith("madrid");
  });

  it("fetches new zone options and resets the zone when the city changes", async () => {
    mockEmptyExemption();
    vi.mocked(fetchZoneOptions).mockResolvedValue([
      { zone_number: "Z9", neighbourhood: "Salamanca" },
    ]);
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(listCities).toHaveBeenCalled());
    await user.selectOptions(screen.getByLabelText("City"), "madrid");

    await waitFor(() => {
      expect(fetchZoneOptions).toHaveBeenCalledWith("madrid");
    });
    expect(await screen.findByRole("option", { name: "Salamanca" })).toBeInTheDocument();
  });

  it("clears the exemption city/zone selection when Clear is clicked", async () => {
    vi.mocked(getSerParkingExemption).mockResolvedValue({
      city_code: "madrid",
      zone_number: "Z1",
    });
    vi.mocked(listCities).mockResolvedValue([{ code: "madrid", name: "Madrid" }]);
    vi.mocked(fetchZoneOptions).mockResolvedValue([
      { zone_number: "Z1", neighbourhood: "Centro" },
    ]);
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(screen.getByLabelText("City")).toHaveValue("madrid"));
    await user.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.getByLabelText("City")).toHaveValue("");
  });

  it("submits the generic payload and calls onUpdated/onClose on success", async () => {
    mockEmptyExemption();
    vi.mocked(updateVehicle).mockResolvedValue(genericVehicle);
    const onUpdated = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={onClose} onUpdated={onUpdated} />,
    );

    await waitFor(() => expect(listCities).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateVehicle).toHaveBeenCalledWith("veh-1", {
        brand: "generic",
        display_name: "My Car",
        license_plate: "1234ABC",
      });
    });
    expect(onUpdated).toHaveBeenCalledWith(genericVehicle);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(setSerParkingExemption).not.toHaveBeenCalled();
    expect(clearSerParkingExemption).not.toHaveBeenCalled();
  });

  it("submits the Toyota payload without a password field when left blank", async () => {
    mockEmptyExemption();
    vi.mocked(updateVehicle).mockResolvedValue(toyotaVehicle);
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={toyotaVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(listCities).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateVehicle).toHaveBeenCalledWith("veh-2", {
        brand: "toyota",
        display_name: "Toyota Car",
        username: "myuser",
        locale: "en_GB",
        license_plate: null,
      });
    });
  });

  it("includes the password field when a new password is entered", async () => {
    mockEmptyExemption();
    vi.mocked(updateVehicle).mockResolvedValue(toyotaVehicle);
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={toyotaVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(listCities).toHaveBeenCalled());
    await user.type(screen.getByLabelText("New Password", { exact: false }), "newpass");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateVehicle).toHaveBeenCalledWith(
        "veh-2",
        expect.objectContaining({ password: "newpass" }),
      );
    });
  });

  it("sets the parking exemption when a city and zone are selected on submit", async () => {
    mockEmptyExemption();
    vi.mocked(fetchZoneOptions).mockResolvedValue([
      { zone_number: "Z9", neighbourhood: "Salamanca" },
    ]);
    vi.mocked(updateVehicle).mockResolvedValue(genericVehicle);
    vi.mocked(setSerParkingExemption).mockResolvedValue({ city_code: "madrid", zone_number: "Z9" });
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(listCities).toHaveBeenCalled());
    await user.selectOptions(screen.getByLabelText("City"), "madrid");
    await waitFor(() => expect(fetchZoneOptions).toHaveBeenCalled());
    await user.selectOptions(screen.getByLabelText("SER Zone"), "Z9");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(setSerParkingExemption).toHaveBeenCalledWith("veh-1", "madrid", "Z9");
    });
  });

  it("clears the exemption via DELETE when one existed and the picker is emptied", async () => {
    vi.mocked(getSerParkingExemption).mockResolvedValue({
      city_code: "madrid",
      zone_number: "Z1",
    });
    vi.mocked(listCities).mockResolvedValue([{ code: "madrid", name: "Madrid" }]);
    vi.mocked(fetchZoneOptions).mockResolvedValue([
      { zone_number: "Z1", neighbourhood: "Centro" },
    ]);
    vi.mocked(updateVehicle).mockResolvedValue(genericVehicle);
    vi.mocked(clearSerParkingExemption).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(screen.getByLabelText("City")).toHaveValue("madrid"));
    await user.click(screen.getByRole("button", { name: "Clear" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(clearSerParkingExemption).toHaveBeenCalledWith("veh-1");
    });
  });

  it("shows an error and does not close when updateVehicle fails", async () => {
    mockEmptyExemption();
    vi.mocked(updateVehicle).mockRejectedValue(new Error("Failed to update vehicle: 500"));
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={onClose} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(listCities).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: "Save" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to update vehicle: 500");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("shows an exemption-specific error and does not close when saving the exemption fails", async () => {
    mockEmptyExemption();
    vi.mocked(fetchZoneOptions).mockResolvedValue([
      { zone_number: "Z9", neighbourhood: "Salamanca" },
    ]);
    vi.mocked(updateVehicle).mockResolvedValue(genericVehicle);
    vi.mocked(setSerParkingExemption).mockRejectedValue(new Error("Failed to set SER parking exemption: 500"));
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={onClose} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(listCities).toHaveBeenCalled());
    await user.selectOptions(screen.getByLabelText("City"), "madrid");
    await waitFor(() => expect(fetchZoneOptions).toHaveBeenCalled());
    await user.selectOptions(screen.getByLabelText("SER Zone"), "Z9");
    await user.click(screen.getByRole("button", { name: "Save" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to set SER parking exemption: 500");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("falls back to the empty cities list when listCities rejects", async () => {
    vi.mocked(getSerParkingExemption).mockResolvedValue({ city_code: null, zone_number: null });
    vi.mocked(listCities).mockRejectedValue(new Error("boom"));
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={vi.fn()} onUpdated={vi.fn()} />,
    );

    await waitFor(() => expect(listCities).toHaveBeenCalled());
    expect(screen.getByLabelText("City")).toHaveValue("");
  });

  it("calls onClose without submitting when Cancel is clicked", async () => {
    mockEmptyExemption();
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <EditVehicleModal vehicle={genericVehicle} onClose={onClose} onUpdated={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(updateVehicle).not.toHaveBeenCalled();
  });
});
