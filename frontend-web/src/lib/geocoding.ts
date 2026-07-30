/**
 * Free destination search via OpenStreetMap's Nominatim public demo API -
 * no API key, same zero-cost/open-source family as the OSRM routing above.
 * Biased toward the user's own city via a viewbox so "Koramangala" resolves
 * to the right one even though several Indian cities have areas with
 * similar names.
 */
export interface GeocodeResult {
  displayName: string;
  lat: number;
  lon: number;
}

export async function searchPlace(query: string, biasLat?: number, biasLon?: number): Promise<GeocodeResult[]> {
  if (query.trim().length < 3) return [];

  const params = new URLSearchParams({
    q: query,
    format: "json",
    limit: "5",
    countrycodes: "in",
  });
  if (biasLat !== undefined && biasLon !== undefined) {
    const delta = 0.5;
    params.set("viewbox", `${biasLon - delta},${biasLat + delta},${biasLon + delta},${biasLat - delta}`);
    params.set("bounded", "0"); // prefer the box but don't hard-exclude results outside it
  }

  try {
    const response = await fetch(`https://nominatim.openstreetmap.org/search?${params.toString()}`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.map((entry: { display_name: string; lat: string; lon: string }) => ({
      displayName: entry.display_name,
      lat: parseFloat(entry.lat),
      lon: parseFloat(entry.lon),
    }));
  } catch {
    return [];
  }
}
