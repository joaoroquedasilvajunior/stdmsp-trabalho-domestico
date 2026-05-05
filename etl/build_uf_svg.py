"""
build_uf_svg.py — One-off builder for the Brazilian UF SVG asset
=================================================================

Fetches a clean GeoJSON of Brazil's 27 federative units, applies a
Mercator projection, and writes dashboard/assets/brazil-uf.svg with each
UF as a labeled <path>. The dashboard reads this file at runtime; the
client-side JS colors the paths by UF code.

This script runs once (or rarely, if we ever update the geometry source).
It does NOT need to be run as part of regular ETL.

Output:
  - dashboard/assets/brazil-uf.svg  (~30 KB simplified, single file, no library)

Each <path> has:
  - id="uf-XX"          (XX = 2-digit IBGE numeric code, matches dim_geo.code)
  - data-sigla="SP"     (2-letter state abbreviation)
  - data-name="São Paulo"  (full PT name, used for tooltips)
  - <title>São Paulo</title>  (accessible name, also used for native tooltip fallback)

Source: github.com/codeforgermany/click_that_hood — IBGE-derived, MIT-licensed,
already simplified to ~50 KB. Stable URL.

Usage:
    cd "/Users/joaoroque/Documents/Claude/Domestic Work"
    python etl/build_uf_svg.py
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
from pathlib import Path

# --- config -------------------------------------------------------------------

GEOJSON_URL = (
    "https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/"
    "public/data/brazil-states.geojson"
)

# Output canvas — designed for a square-ish container; the dashboard CSS can
# scale this freely via viewBox.
WIDTH = 600
HEIGHT = 600

ROOT = Path(__file__).parent.parent
OUT_PATH = ROOT / "dashboard" / "assets" / "brazil-uf.svg"

# IBGE conventions ↔ source GeoJSON property names. The click_that_hood file
# carries the full state name in `name`; we map name → IBGE code (matches
# dim_geo.code in our schema) and name → 2-letter sigla (for tooltips).
NAME_TO_CODE = {
    "Acre": "12", "Alagoas": "27", "Amapá": "16", "Amazonas": "13",
    "Bahia": "29", "Ceará": "23", "Distrito Federal": "53",
    "Espírito Santo": "32", "Goiás": "52", "Maranhão": "21",
    "Mato Grosso": "51", "Mato Grosso do Sul": "50", "Minas Gerais": "31",
    "Pará": "15", "Paraíba": "25", "Paraná": "41", "Pernambuco": "26",
    "Piauí": "22", "Rio de Janeiro": "33", "Rio Grande do Norte": "24",
    "Rio Grande do Sul": "43", "Rondônia": "11", "Roraima": "14",
    "Santa Catarina": "42", "São Paulo": "35", "Sergipe": "28",
    "Tocantins": "17",
}
NAME_TO_SIGLA = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM",
    "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF",
    "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA",
    "Mato Grosso": "MT", "Mato Grosso do Sul": "MS", "Minas Gerais": "MG",
    "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE",
    "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR",
    "Santa Catarina": "SC", "São Paulo": "SP", "Sergipe": "SE",
    "Tocantins": "TO",
}


# --- projection ---------------------------------------------------------------

def _count_points(geom: dict) -> int:
    """Total number of (lon, lat) points across all rings of a geometry."""
    if geom["type"] == "Polygon":
        return sum(len(r) for r in geom["coordinates"])
    if geom["type"] == "MultiPolygon":
        return sum(len(r) for poly in geom["coordinates"] for r in poly)
    return 0


def _perp_distance(p, a, b):
    """Perpendicular distance from point p to line segment ab, in 2D."""
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    # Distance from point to line through a, b
    return abs(dy * px - dx * py + bx * ay - by * ax) / math.hypot(dx, dy)


def rdp_simplify(points: list, epsilon: float) -> list:
    """Ramer–Douglas–Peucker simplification of a polyline (or polygon ring).

    Removes points whose perpendicular distance to the simplified line falls
    below epsilon. Iterative implementation to avoid Python's recursion limit
    for long coastlines.
    """
    if len(points) <= 2:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        max_d = 0.0
        max_i = -1
        a, b = points[start], points[end]
        for i in range(start + 1, end):
            d = _perp_distance(points[i], a, b)
            if d > max_d:
                max_d = d
                max_i = i
        if max_d > epsilon and max_i != -1:
            keep[max_i] = True
            stack.append((start, max_i))
            stack.append((max_i, end))
    return [p for p, k in zip(points, keep) if k]


def simplify_geometry(geom: dict, epsilon: float) -> dict:
    """Apply RDP simplification to every ring of a Polygon or MultiPolygon.
    Drops rings that collapse to fewer than 4 points after simplification
    (a polygon needs >=4 points: first==last, plus at least 3 distinct corners).
    """
    def _simplify_ring(ring):
        # GeoJSON coords are [lon, lat] pairs; cast to tuples for hashing if needed.
        pts = [(c[0], c[1]) for c in ring]
        if len(pts) <= 4:
            return ring
        simp = rdp_simplify(pts, epsilon)
        # Ensure closed ring (first == last)
        if simp[0] != simp[-1]:
            simp.append(simp[0])
        if len(simp) < 4:
            return None
        return [list(p) for p in simp]

    g = {"type": geom["type"]}
    if geom["type"] == "Polygon":
        rings = []
        for ring in geom["coordinates"]:
            r = _simplify_ring(ring)
            if r:
                rings.append(r)
        g["coordinates"] = rings
    elif geom["type"] == "MultiPolygon":
        polys = []
        for poly in geom["coordinates"]:
            rings = []
            for ring in poly:
                r = _simplify_ring(ring)
                if r:
                    rings.append(r)
            if rings:
                polys.append(rings)
        g["coordinates"] = polys
    else:
        g["coordinates"] = geom["coordinates"]
    return g


def make_projection(features: list, w: int, h: int, padding: int = 8):
    """Compute an equirectangular projection fitted to the bounding box of
    the given GeoJSON features. Returns a closure (lon, lat) → (x, y) in
    SVG canvas coordinates.

    For a small national-scale map at low-to-mid latitudes (Brazil:
    bbox center ≈ -14°), equirectangular with a cos(lat_center) longitude
    correction is visually indistinguishable from Mercator and avoids the
    unit-mixing trap (lon in degrees vs lat in log-Mercator).
    """
    lon_min, lat_min = math.inf, math.inf
    lon_max, lat_max = -math.inf, -math.inf

    def visit_coords(geom):
        nonlocal lon_min, lat_min, lon_max, lat_max
        if geom["type"] == "Polygon":
            for ring in geom["coordinates"]:
                for lon, lat in ring:
                    lon_min = min(lon_min, lon); lon_max = max(lon_max, lon)
                    lat_min = min(lat_min, lat); lat_max = max(lat_max, lat)
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    for lon, lat in ring:
                        lon_min = min(lon_min, lon); lon_max = max(lon_max, lon)
                        lat_min = min(lat_min, lat); lat_max = max(lat_max, lat)

    for f in features:
        visit_coords(f["geometry"])

    # Compress longitude by cos(latitude_center) so 1° lon ≈ 1° lat in
    # apparent distance at the bbox center. Without this correction, the
    # map looks horizontally stretched at non-equatorial latitudes.
    lat_center = (lat_min + lat_max) / 2
    lon_scale_factor = math.cos(math.radians(lat_center))

    span_lon_corrected = (lon_max - lon_min) * lon_scale_factor
    span_lat = lat_max - lat_min

    scale_x = (w - 2 * padding) / span_lon_corrected
    scale_y = (h - 2 * padding) / span_lat
    scale = min(scale_x, scale_y)   # uniform scale → no distortion

    used_w = span_lon_corrected * scale
    used_h = span_lat * scale
    offset_x = padding + (w - 2 * padding - used_w) / 2
    offset_y = padding + (h - 2 * padding - used_h) / 2

    def project(lon, lat):
        # SVG y-axis points down → flip latitude
        x = offset_x + (lon - lon_min) * lon_scale_factor * scale
        y = offset_y + (lat_max - lat) * scale
        return x, y

    return project, (lon_min, lat_min, lon_max, lat_max)


# --- path construction --------------------------------------------------------

def ring_to_path(ring, project) -> str:
    """Convert one ring (list of [lon, lat] pairs) to an SVG sub-path."""
    if not ring:
        return ""
    parts = []
    for i, pt in enumerate(ring):
        lon, lat = pt[0], pt[1]
        x, y = project(lon, lat)
        cmd = "M" if i == 0 else "L"
        parts.append(f"{cmd}{x:.1f},{y:.1f}")
    parts.append("Z")
    return " ".join(parts)


def geometry_to_d(geom, project) -> str:
    """Convert a Polygon or MultiPolygon geometry to a complete SVG `d` string."""
    if geom["type"] == "Polygon":
        return " ".join(ring_to_path(ring, project) for ring in geom["coordinates"])
    elif geom["type"] == "MultiPolygon":
        return " ".join(
            ring_to_path(ring, project)
            for poly in geom["coordinates"]
            for ring in poly
        )
    else:
        raise ValueError(f"Unexpected geometry type: {geom['type']}")


# --- main --------------------------------------------------------------------

def main():
    cache_path = ROOT / "etl" / "raw" / "brazil-uf.geojson"
    if cache_path.exists() and cache_path.stat().st_size > 1024:
        print(f"reading cached geometry from {cache_path}")
        gj = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        print(f"fetching {GEOJSON_URL} …")
        req = urllib.request.Request(GEOJSON_URL, headers={"User-Agent": "build_uf_svg"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
        gj = json.loads(raw)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(raw, encoding="utf-8")
        print(f"cached geometry at {cache_path} ({cache_path.stat().st_size // 1024} KB)")

    features = gj.get("features") or []
    if len(features) != 27:
        print(f"WARNING: expected 27 UFs, got {len(features)}", file=sys.stderr)

    # Map source-name → our IBGE numeric code; bail loudly on missing names.
    enriched = []
    missing = []
    for f in features:
        name = f["properties"].get("name") or f["properties"].get("NAME")
        if name not in NAME_TO_CODE:
            missing.append(name)
            continue
        enriched.append({
            "name": name,
            "code": NAME_TO_CODE[name],
            "sigla": NAME_TO_SIGLA[name],
            "geometry": f["geometry"],
        })
    if missing:
        print(f"ERROR: {len(missing)} feature(s) had unknown names: {missing}", file=sys.stderr)
        sys.exit(1)

    # Simplify geometry: epsilon in lon/lat degrees. 0.05° ≈ 5.5 km, plenty
    # for a state-level dashboard map. Cuts file size from ~1 MB to ~30–80 KB
    # without visible loss at typical display sizes.
    EPSILON = 0.05
    pts_before = sum(_count_points(f["geometry"]) for f in enriched)
    for f in enriched:
        f["geometry"] = simplify_geometry(f["geometry"], EPSILON)
    pts_after = sum(_count_points(f["geometry"]) for f in enriched)
    print(f"simplified geometry (RDP, epsilon={EPSILON}°): {pts_before:,} → {pts_after:,} points "
          f"({100 * pts_after / pts_before:.1f}% retained)")

    project, bbox = make_projection(features, WIDTH, HEIGHT)
    print(f"fitted bbox: lon=[{bbox[0]:.2f}, {bbox[2]:.2f}]  lat=[{bbox[1]:.2f}, {bbox[3]:.2f}]")

    # Sort by code so the SVG source is stable and easy to diff
    enriched.sort(key=lambda f: f["code"])

    paths = []
    for f in enriched:
        d = geometry_to_d(f["geometry"], project)
        # Use double quotes inside the SVG; escape the name for HTML safety
        name_safe = f["name"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        paths.append(
            f'  <path id="uf-{f["code"]}" data-sigla="{f["sigla"]}" '
            f'data-name="{name_safe}" d="{d}">\n'
            f'    <title>{name_safe}</title>\n'
            f'  </path>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'role="img" aria-label="Mapa do Brasil — Unidades da Federação" '
        f'class="brazil-uf-map">\n'
        f'{chr(10).join(paths)}\n'
        f'</svg>\n'
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(svg, encoding="utf-8")
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"wrote {OUT_PATH} ({size_kb:.1f} KB, {len(enriched)} UFs)")


if __name__ == "__main__":
    main()
