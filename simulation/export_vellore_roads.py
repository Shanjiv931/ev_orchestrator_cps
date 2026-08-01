"""One-off export: reads the real Vellore SUMO network and writes a compact
JSON of drivable road centerlines in lon/lat, for the Godot viewer to render
as an actual road mesh instead of a flat ground plane.

Run inside the sim-vellore container (has sumolib + the net file mounted):
    docker compose run --rm sim-vellore python export_vellore_roads.py
"""
import json

import sumolib

net = sumolib.net.readNet("sumo/vellore/vellore.net.xml")

roads = []
min_lon = min_lat = 1e9
max_lon = max_lat = -1e9

for edge in net.getEdges():
    if edge.getFunction() == "internal" or not edge.allows("passenger"):
        continue
    lanes = edge.getLanes()
    if not lanes:
        continue
    shape = lanes[len(lanes) // 2].getShape()
    points = []
    for x, y in shape:
        lon, lat = net.convertXY2LonLat(x, y)
        points.append([round(lon, 6), round(lat, 6)])
        min_lon, max_lon = min(min_lon, lon), max(max_lon, lon)
        min_lat, max_lat = min(min_lat, lat), max(max_lat, lat)
    if len(points) < 2:
        continue
    roads.append({"lanes": len(lanes), "points": points})

output = {
    "bounds": {"min_lon": round(min_lon, 6), "min_lat": round(min_lat, 6),
               "max_lon": round(max_lon, 6), "max_lat": round(max_lat, 6)},
    "roads": roads,
}
with open("vellore_roads_export.json", "w") as f:
    json.dump(output, f)

print(f"wrote {len(roads)} road segments, bounds={output['bounds']}")
