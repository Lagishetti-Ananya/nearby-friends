import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import { useEffect } from "react";

const selfIcon = new L.DivIcon({
  className: "pin pin-self",
  html: '<span class="pin-dot"></span>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const friendIcon = new L.DivIcon({
  className: "pin pin-friend",
  html: '<span class="pin-dot"></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function Recenter({ lat, lon }) {
  const map = useMap();
  useEffect(() => {
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      map.setView([lat, lon], map.getZoom() || 13, { animate: true });
    }
  }, [lat, lon, map]);
  return null;
}

export default function MapView({ self, friends }) {
  const center = self ? [self.lat, self.lon] : [37.7749, -122.4194];
  return (
    <MapContainer center={center} zoom={13} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {self && (
        <>
          <Recenter lat={self.lat} lon={self.lon} />
          <Marker position={[self.lat, self.lon]} icon={selfIcon}>
            <Popup>
              <strong>You</strong>
              <div>Last update: {self.updatedAt || "—"}</div>
            </Popup>
          </Marker>
        </>
      )}
      {friends.map((f) => (
        <Marker key={f.user_id} position={[f.latitude, f.longitude]} icon={friendIcon}>
          <Popup>
            <strong>{f.name}</strong>
            <div>{f.distance_miles.toFixed(2)} miles away</div>
            <div>Updated {new Date(f.updated_at).toLocaleTimeString()}</div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
