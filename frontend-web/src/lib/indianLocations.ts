export interface CityOption {
  city: string;
  lat: number;
  lon: number;
}

export const INDIAN_STATES: Record<string, CityOption[]> = {
  Karnataka: [
    { city: "Bengaluru", lat: 12.9716, lon: 77.5946 },
    { city: "Mysuru", lat: 12.2958, lon: 76.6394 },
  ],
  Maharashtra: [
    { city: "Mumbai", lat: 19.076, lon: 72.8777 },
    { city: "Pune", lat: 18.5204, lon: 73.8567 },
    { city: "Nagpur", lat: 21.1458, lon: 79.0882 },
  ],
  Delhi: [{ city: "New Delhi", lat: 28.6139, lon: 77.209 }],
  "Tamil Nadu": [
    { city: "Chennai", lat: 13.0827, lon: 80.2707 },
    { city: "Coimbatore", lat: 11.0168, lon: 76.9558 },
  ],
  Telangana: [{ city: "Hyderabad", lat: 17.385, lon: 78.4867 }],
  "West Bengal": [{ city: "Kolkata", lat: 22.5726, lon: 88.3639 }],
  Gujarat: [
    { city: "Ahmedabad", lat: 23.0225, lon: 72.5714 },
    { city: "Surat", lat: 21.1702, lon: 72.8311 },
  ],
  Rajasthan: [{ city: "Jaipur", lat: 26.9124, lon: 75.7873 }],
  "Uttar Pradesh": [
    { city: "Lucknow", lat: 26.8467, lon: 80.9462 },
    { city: "Noida", lat: 28.5355, lon: 77.391 },
  ],
  Kerala: [{ city: "Kochi", lat: 9.9312, lon: 76.2673 }],
  Punjab: [{ city: "Chandigarh", lat: 30.7333, lon: 76.7794 }],
};

export function findNearestCity(lat: number, lon: number): { state: string; city: string } | null {
  let best: { state: string; city: string; distance: number } | null = null;
  for (const [state, cities] of Object.entries(INDIAN_STATES)) {
    for (const c of cities) {
      const distance = Math.hypot(c.lat - lat, c.lon - lon);
      if (!best || distance < best.distance) best = { state, city: c.city, distance };
    }
  }
  return best ? { state: best.state, city: best.city } : null;
}
