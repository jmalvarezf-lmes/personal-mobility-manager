import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useTranslation } from "react-i18next";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { getSerTicketHistory } from "../api/vehicles";
import type { SerTicket, VehicleListItem } from "../types/vehicle";
import { formatInTimezone } from "../utils/timezone";
import HistoryModal, { OSM_FALLBACK } from "./HistoryModal";

// Same car-style DivIcon used for the single marker on
// VehicleLocationHistoryModal's newest pin, reused here for visual
// consistency (see add-ser-ticket-history-ui spec: "visually consistent
// with VehicleLocationHistoryModal's map").
const ticketIcon = L.divIcon({
  html: '<div style="font-size:24px;line-height:1">🚗</div>',
  className: "",
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

interface VehicleSerTicketHistoryModalProps {
  vehicle: VehicleListItem;
  onClose: () => void;
}

function provenanceLabel(autoCreated: boolean | null, t: (key: string) => string): string {
  if (autoCreated === true) return t("modal.serTickets.provenanceAuto");
  if (autoCreated === false) return t("modal.serTickets.provenanceManual");
  return t("modal.serTickets.provenanceUnknown");
}

// Task 14.6: distinct, Tailwind-palette-consistent colors per provenance
// state — previously all three states shared `bg-blue-100 text-blue-700`
// (the same classes as the brand tag elsewhere), making them distinguishable
// only by text. Green/amber aren't used anywhere else in the frontend yet,
// so they're introduced fresh here rather than colliding with an existing
// meaning (blue = brand, gray = neutral, red = destructive).
function provenanceBadgeClassName(autoCreated: boolean | null): string {
  if (autoCreated === true) return "bg-green-100 text-green-700";
  if (autoCreated === false) return "bg-gray-100 text-gray-700";
  return "bg-amber-100 text-amber-700";
}

function cityLabel(ticket: SerTicket, t: (key: string) => string): string {
  if (ticket.city_name) return ticket.city_name;
  if (ticket.city_code) return ticket.city_code;
  return t("modal.serTickets.unknownCity");
}

export default function VehicleSerTicketHistoryModal({
  vehicle,
  onClose,
}: VehicleSerTicketHistoryModalProps) {
  const { t } = useTranslation();

  return (
    <HistoryModal<SerTicket>
      title={t("modal.serTickets.title", { name: vehicle.display_name })}
      onClose={onClose}
      vehicleId={vehicle.vehicle_id}
      fetchPage={getSerTicketHistory}
      contentClassName="flex flex-1 flex-col gap-4 overflow-y-auto"
      messages={{
        loading: t("modal.serTickets.loading"),
        loadingMore: t("modal.serTickets.loadingMore"),
        loadMore: t("modal.serTickets.loadMore"),
        empty: t("modal.serTickets.empty"),
        error: t("modal.serTickets.error"),
      }}
    >
      {({ items: tickets, displayTimezone }) => (
        <>
          {tickets.map((ticket) => (
            <div
              key={ticket.id}
              className="flex flex-col gap-2 rounded border border-gray-200 p-3"
            >
              {ticket.latitude !== null && ticket.longitude !== null && (
                <div className="h-40 shrink-0 overflow-hidden rounded border border-gray-200">
                  <MapContainer
                    center={[ticket.latitude, ticket.longitude]}
                    zoom={15}
                    className="h-full w-full"
                  >
                    <TileLayer
                      url={OSM_FALLBACK}
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    />
                    <Marker position={[ticket.latitude, ticket.longitude]} icon={ticketIcon}>
                      <Popup>{formatInTimezone(ticket.start_date, displayTimezone)}</Popup>
                    </Marker>
                  </MapContainer>
                </div>
              )}

              <div className="space-y-1 text-sm text-gray-600">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-800">
                    {cityLabel(ticket, t)}
                    {ticket.zone_number ? ` — ${t("modal.serTickets.zone")} ${ticket.zone_number}` : ""}
                  </span>
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${provenanceBadgeClassName(ticket.auto_created)}`}
                  >
                    {provenanceLabel(ticket.auto_created, t)}
                  </span>
                </div>
                <p>
                  {t("modal.serTickets.startDate")}: {formatInTimezone(ticket.start_date, displayTimezone)}
                </p>
                <p>
                  {t("modal.serTickets.endDate")}: {formatInTimezone(ticket.end_date, displayTimezone)}
                </p>
              </div>
            </div>
          ))}
        </>
      )}
    </HistoryModal>
  );
}
