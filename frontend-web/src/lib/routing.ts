/**
 * Real routing via OSRM's public demo server (router.project-osrm.org) -
 * free, open-source, no API key. This is the public demo instance, fine for
 * this project's personal/academic-scale traffic; a production deployment
 * would self-host OSRM instead (still free/open-source, just not subject to
 * the demo server's fair-use limits). No paid mapping API (Google
 * Directions, Mapbox, etc.) is used anywhere in this app.
 */
export interface RouteResult {
  coordinates: [number, number][]; // [lat, lon] pairs, ready for a Leaflet Polyline
  distanceKm: number;
  durationMinutes: number;
}

export async function fetchRoute(
  fromLat: number, fromLon: number, toLat: number, toLon: number,
): Promise<RouteResult | null> {
  const url = `https://router.project-osrm.org/route/v1/driving/${fromLon},${fromLat};${toLon},${toLat}?overview=full&geometries=geojson`;
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const data = await response.json();
    const route = data.routes?.[0];
    if (!route) return null;
    const coordinates: [number, number][] = route.geometry.coordinates.map(
      ([lon, lat]: [number, number]) => [lat, lon],
    );
    return {
      coordinates,
      distanceKm: route.distance / 1000,
      durationMinutes: route.duration / 60,
    };
  } catch {
    return null;
  }
}

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
