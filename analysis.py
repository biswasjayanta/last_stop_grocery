"""
Last Stop: Groceries: data preparation and analysis
====================================================

Reproduces the neighbourhood data embedded in index.html and every figure quoted
in WRITEUP.md, for the UNC Charlotte GIS Day 2026 AI Interactive GeoVisualization
Competition (topic: Food Security).

Inputs (paths relative to the project folder, by default the folder above this file):

    qol_data/Data_Download_20261002.csv        Quality of Life Explorer, all variables by NPA and year
    qol_data/QOL_NPA_2020_final_projected.shp  Quality of Life Explorer, 2020 Neighborhood Profile Areas
    Data/blue_line_stops.geojson               LYNX Blue Line stations (City of Charlotte Open Data)
    Data/gold_line_stops.geojson               LYNX Gold Line stops
    Data/blue_line_walk.geojson                5/10/15 minute network walksheds around Blue Line stations
    Data/gold_line_walk.geojson                ... around Gold Line stops
    Data/blue_line_pop_build.xls               WorldPop 2025 residents and building counts per station walkshed
    Data/gold_line_pop_build.xls
    DataGrocery/grocery_stores.geojson         161 grocery stores (City of Charlotte Open Data)
    DataGrocery/grocery_stores_walk.geojson    5/10/15 minute network walksheds around each store

Outputs (written to analysis_output/ next to this file):

    qol_npa_food.json   neighbourhood data embedded in index.html as <script id="qol">
    npa_need.csv        one row per NPA: values, percentile ranks, need index, classes, rail coverage
    station_need.csv    one row per station: grocery access, need score, priority flag
    summary.json        the figures quoted in WRITEUP.md

Usage:

    python analysis.py                     # project folder = parent of this file
    python analysis.py --root PATH         # or point at the folder that holds qol_data/, Data/, DataGrocery/
    python analysis.py --embed index.html  # also replace the <script id="qol"> data in a page

Requires Python 3.9+, geopandas, pandas, numpy, shapely, and xlrd (for the .xls population tables).

The map recomputes the need index in the browser when weights change. This script
uses the default (equal) weights and the same rules, so its numbers match the
map's default view.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.ops import unary_union

# --------------------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------------------

CRS_WEB = 4326     # WGS 84, for the web map
CRS_AREA = 2264    # NAD83 / North Carolina State Plane (US feet), the QoL NPAs' native CRS
SIMPLIFY_FT = 40   # polygon simplification tolerance for the web, in feet
WALK_TIMES = (5, 10, 15)
MIN_SHED_SHARE = 0.02  # keep NPAs that hold at least 2% of a station's walkshed area

# Quality of Life Explorer variables: key -> (variable_id, column to use)
QOL_VARS = {
    "snap":    (80, "normalized"),  # % residents receiving public nutrition assistance
    "groc":    (45, "normalized"),  # % housing units within 1/2 mile of a chain grocery store
    "grocU":   (45, "raw"),         # housing units within 1/2 mile of a chain grocery store
    "inc":     (37, "normalized"),  # median household income ($)
    "transit": (36, "normalized"),  # % housing units within 1/2 mile of a transit stop
    "drive":   (10, "normalized"),  # % workers who drive to work alone
    "pop":     (47, "raw"),         # population
    "hu":      (5,  "raw"),         # housing units
}

# Need index: measure -> direction (+1 = a higher value means more need)
NEED = {"snap": +1, "inc": -1, "groc": -1, "drive": -1}
WEIGHTS = {"snap": 1, "inc": 1, "groc": 1, "drive": 1}

UPTOWN_STATION = ("blue", "Charlotte Transportation Center/Arena")  # reference point for "Uptown"


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def haversine_m(lon1, lat1, lon2, lat2):
    """Great-circle distance in metres (same formula as the map's straight-line distances)."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def bearing_deg(lon1, lat1, lon2, lat2):
    """Initial compass bearing from point 1 to point 2, 0-360 degrees."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def sector8(b):
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int(((b + 22.5) % 360) // 45)]


def mid_percentile(sorted_vals, v):
    """Share of values below v, counting ties as half (matches the map's ranking)."""
    lo, hi = bisect.bisect_left(sorted_vals, v), bisect.bisect_right(sorted_vals, v)
    return (lo + hi) / 2 / len(sorted_vals)


def parse_shed_name(name):
    """'Tom Hunter : 0 - 15' -> ('Tom Hunter', 15)."""
    m = re.match(r"^(.*?)\s*:\s*0\s*-\s*(\d+)\s*$", str(name).strip())
    return m.group(1).strip(), int(m.group(2))


def round_geom(geom, nd=5):
    """Polygon/MultiPolygon -> nested lists [[ring, hole...], ...] of rounded lon/lat."""
    def ring(r):
        out = []
        for x, y in r.coords:
            p = [round(x, nd), round(y, nd)]
            if not out or out[-1] != p:
                out.append(p)
        return out
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    return [[ring(p.exterior)] + [ring(i) for i in p.interiors] for p in polys]


def num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(float(v), 1) if abs(v) < 1000 else int(round(v))


def read_geojson(path):
    g = gpd.read_file(path)
    if g.crs is None:
        g = g.set_crs(CRS_WEB)
    return g.to_crs(CRS_WEB)


def strip_prefix(df):
    """Drop 'layer.' prefixes that ArcGIS joins add to field names."""
    df = df.copy()
    df.columns = [c.split(".")[-1] if c != "geometry" else c for c in df.columns]
    return df.loc[:, ~df.columns.duplicated()]


# --------------------------------------------------------------------------------------
# 1. Quality of Life Explorer
# --------------------------------------------------------------------------------------

def load_qol(root: Path):
    table = pd.read_csv(root / "qol_data" / "Data_Download_20261002.csv")
    assert not table.duplicated(["variable_id", "NPA", "data_year"]).any()

    npa = gpd.read_file(root / "qol_data" / "QOL_NPA_2020_final_projected.shp")
    npa = npa[["NPA2020_No", "City", "geometry"]].rename(columns={"NPA2020_No": "npa"})
    npa = npa.to_crs(CRS_AREA)
    npa["geometry"] = npa.geometry.buffer(0)

    years = {}
    for key, (vid, col) in QOL_VARS.items():
        rows = table[table.variable_id == vid]
        year = int(rows.data_year.max())
        years[key] = year
        npa[key] = npa.npa.map(rows[rows.data_year == year].set_index("NPA")[col])

    # Grocery proximity 2025 is blank for many NPAs, with almost no explicit zeros;
    # in 2022 every NPA had a value and most of today's blanks were 0%. Read blanks as 0%.
    g = table[table.variable_id == 45].pivot(index="NPA", columns="data_year", values="normalized")
    blank = npa.groc.isna()
    was_zero = g.loc[npa.npa[blank], 2022].eq(0).mean()
    grocery_blank = {
        "blank_latest": int(blank.sum()),
        "explicit_zero_latest": int((npa.groc == 0).sum()),
        "share_of_blanks_zero_in_2022": round(float(was_zero), 3),
        "zero_in_2022": int((g[2022] == 0).sum()),
    }
    npa["gb"] = blank.astype(int)
    npa["groc"] = npa.groc.fillna(0)
    npa["grocU"] = npa.grocU.fillna(0)
    npa["ok"] = npa["pop"].fillna(0) > 0   # NPAs with residents enter the rankings
    return npa, years, grocery_blank


def need_index(npa: gpd.GeoDataFrame):
    ok = npa[npa.ok]
    for k, d in NEED.items():
        vals = sorted(ok[k].dropna())
        npa["r_" + k] = [
            (mid_percentile(vals, v) if d > 0 else 1 - mid_percentile(vals, v))
            if (o and not pd.isna(v)) else np.nan
            for v, o in zip(npa[k], npa.ok)
        ]

    def score(row):
        if not row.ok:
            return np.nan
        a = b = 0.0
        for k in NEED:
            r = row["r_" + k]
            if not pd.isna(r) and WEIGHTS[k] > 0:
                a += WEIGHTS[k] * r
                b += WEIGHTS[k]
        return a / b if b else np.nan

    npa["score"] = npa.apply(score, axis=1)
    breaks = np.quantile(npa.score.dropna(), [0.2, 0.4, 0.6, 0.8])  # same as d3.quantile
    npa["quintile"] = [0 if pd.isna(s) else 1 + bisect.bisect_right(list(breaks), s) for s in npa.score]
    npa["rank"] = npa.score.rank(ascending=False, method="first").astype("Int64")

    # bivariate classes: food-assistance terciles x grocery proximity (none / below median / above)
    snap_q = np.quantile(npa.loc[npa.ok, "snap"].dropna(), [1 / 3, 2 / 3])
    groc_med = float(np.median(npa.loc[npa.ok & (npa.groc > 0), "groc"]))

    def bi(row):
        if not row.ok or pd.isna(row.snap):
            return None
        i = 0 if row.snap < snap_q[0] else 1 if row.snap < snap_q[1] else 2
        j = 2 if row.groc == 0 else 1 if row.groc < groc_med else 0
        return f"{i}{j}"

    npa["bivariate"] = npa.apply(bi, axis=1)
    return breaks, snap_q, groc_med


# --------------------------------------------------------------------------------------
# 2. LYNX stations, grocery stores and walksheds
# --------------------------------------------------------------------------------------

def load_network(root: Path):
    stops = {
        "blue": strip_prefix(read_geojson(root / "Data" / "blue_line_stops.geojson")).rename(columns={"NAME": "name"}),
        "gold": strip_prefix(read_geojson(root / "Data" / "gold_line_stops.geojson")).rename(columns={"Stop_Name": "name"}),
    }
    for st in stops.values():
        st["name"] = st["name"].astype(str).str.strip()
    sheds, people = {}, {}
    for line in ("blue", "gold"):
        s = strip_prefix(read_geojson(root / "Data" / f"{line}_line_walk.geojson"))
        s[["name", "t"]] = s.Name.apply(lambda n: pd.Series(parse_shed_name(n)))
        s["geometry"] = s.geometry.buffer(0)
        sheds[line] = s[["name", "t", "geometry"]]
        x = pd.read_excel(root / "Data" / f"{line}_line_pop_build.xls")
        x[["name", "t"]] = x.Name.apply(lambda n: pd.Series(parse_shed_name(n)))
        people[line] = x.set_index(["name", "t"])["Population"]
        missing = set(stops[line].name) - set(s.name)
        if missing:
            print(f"  note: no walkshed for {line} stations {sorted(missing)}")

    stores = strip_prefix(read_geojson(root / "DataGrocery" / "grocery_stores.geojson"))
    stores["AddressID"] = stores.AddressID.astype(str).str.strip()
    gw = strip_prefix(read_geojson(root / "DataGrocery" / "grocery_stores_walk.geojson"))
    gw[["AddressID", "t"]] = gw.Name.apply(lambda n: pd.Series(parse_shed_name(n)))
    gw["geometry"] = gw.geometry.buffer(0)
    return stops, sheds, people, stores, gw[["AddressID", "t", "geometry"]]


def station_access(stops, stores, gw):
    """A station reaches a store within t minutes when it lies inside that store's t-minute walkshed."""
    rows = []
    for line, st in stops.items():
        for _, s in st.iterrows():
            best = None
            for t in WALK_TIMES:
                if gw[(gw.t == t)].contains(s.geometry).any():
                    best = t
                    break
            near = min(((haversine_m(s.geometry.x, s.geometry.y, g.geometry.x, g.geometry.y), g.Name)
                        for _, g in stores.iterrows()))
            rows.append({"line": line, "station": s["name"], "lon": s.geometry.x, "lat": s.geometry.y,
                         "reach_min": best, "nearest_store": near[1], "nearest_store_m": round(near[0])})
    return pd.DataFrame(rows)


def station_sheds(sheds):
    """Each station's 15 minute walkshed (10 minute where no 15 minute area exists)."""
    out = {}
    for line, s in sheds.items():
        for name, grp in s.groupby("name"):
            by_t = dict(zip(grp.t, grp.geometry))
            out[(line, name)] = by_t.get(15) or by_t.get(10)
    return out


# --------------------------------------------------------------------------------------
# 3. Analysis
# --------------------------------------------------------------------------------------

def run(root: Path, out: Path, embed: Path | None):
    out.mkdir(parents=True, exist_ok=True)
    print("Reading Quality of Life Explorer data ...")
    npa, years, grocery_blank = load_qol(root)
    breaks, snap_q, groc_med = need_index(npa)

    print("Reading stations, stores and walksheds ...")
    stops, sheds, people, stores, gw = load_network(root)
    acc = station_access(stops, stores, gw)
    shed15 = station_sheds(sheds)

    # station walkshed -> NPA area shares (State Plane feet)
    npa_a = npa.set_index("npa")
    sw = {}
    for (line, name), geom in shed15.items():
        g = gpd.GeoSeries([geom], crs=CRS_WEB).to_crs(CRS_AREA).iloc[0]
        share = npa_a.geometry.intersection(g).area / g.area
        share = share[share >= MIN_SHED_SHARE].sort_values(ascending=False)
        sw[f"{line}|{name}"] = [[int(i), round(float(f), 3)] for i, f in share.items()]

    # station need = area-weighted mean need index of the NPAs its walkshed covers
    def st_need(key):
        a = b = 0.0
        for i, f in sw.get(key, []):
            sc = npa_a.at[i, "score"]
            if not pd.isna(sc):
                a += f * sc
                b += f
        return a / b if b else np.nan

    acc["need"] = [st_need(f"{l}|{n}") for l, n in zip(acc.line, acc.station)]
    acc["need_quintile"] = [0 if pd.isna(s) else 1 + bisect.bisect_right(list(breaks), s) for s in acc.need]
    acc["residents_15min"] = [people[l].get((n, 15), people[l].get((n, 10), np.nan)) for l, n in zip(acc.line, acc.station)]
    acc["priority_15min"] = (acc.need_quintile == 5) & (acc.reach_min.isna())

    # how much of each NPA lies within a 15 minute walk of a LYNX station / of a grocery store
    rail_union = gpd.GeoSeries([unary_union(list(shed15.values()))], crs=CRS_WEB).to_crs(CRS_AREA).iloc[0]
    groc_union = gpd.GeoSeries([unary_union(list(gw[gw.t == 15].geometry))], crs=CRS_WEB).to_crs(CRS_AREA).iloc[0]
    npa["rail15_share"] = npa.geometry.intersection(rail_union).area / npa.geometry.area
    npa["groc15_share"] = npa.geometry.intersection(groc_union).area / npa.geometry.area

    # location relative to Uptown, and distance to the nearest LYNX station
    up = acc[(acc.line == UPTOWN_STATION[0]) & (acc.station == UPTOWN_STATION[1])].iloc[0]
    rp = npa.to_crs(CRS_WEB).geometry.representative_point()
    npa["lon"], npa["lat"] = rp.x, rp.y
    npa["sector"] = [sector8(bearing_deg(up.lon, up.lat, x, y)) for x, y in zip(npa.lon, npa.lat)]
    npa["nearest_station_m"] = [min(haversine_m(x, y, a, b) for a, b in zip(acc.lon, acc.lat)) for x, y in zip(npa.lon, npa.lat)]

    # ---------------- figures quoted in the write-up ----------------
    pop_ok = npa[npa.ok]
    top = pop_ok[pop_ok.quintile == 5]
    area_share = lambda d, col: float((d[col] * d.geometry.area).sum() / d.geometry.area.sum())
    south = top.sector.isin(["SE", "S", "SW"])
    hh = pop_ok[pop_ok.bivariate == "22"]
    prio = acc[acc.priority_15min].sort_values("residents_15min", ascending=False)

    def stations_reaching(t):
        return {l: int(((acc.line == l) & acc.reach_min.notna() & (acc.reach_min <= t)).sum()) for l in ("blue", "gold")}

    summary = {
        "settings": {"weights": WEIGHTS, "walk_minutes": 15, "chains": "all"},
        "qol_years": years,
        "grocery_proximity_blanks": grocery_blank,
        "npas": {"total": int(len(npa)), "populated": int(npa.ok.sum()), "population_2020": int(pop_ok["pop"].sum())},
        "bivariate_breaks": {"food_assistance_terciles_pct": [round(float(v), 1) for v in snap_q],
                             "grocery_proximity_median_of_nonzero_pct": round(groc_med, 1)},
        "high_food_assistance_and_no_grocery": {"npas": int(len(hh)), "population": int(hh["pop"].sum())},
        "top20_need": {
            "npas": int(len(top)),
            "population": int(top["pop"].sum()),
            "no_chain_grocery_within_half_mile": {"npas": int((top.groc == 0).sum()),
                                                  "population": int(top.loc[top.groc == 0, "pop"].sum())},
            "land_share_within_15min_walk_of_grocery": round(area_share(top, "groc15_share"), 3),
            "land_share_within_15min_walk_of_grocery_all_populated": round(area_share(pop_ok, "groc15_share"), 3),
            "by_sector_from_uptown": top.sector.value_counts().to_dict(),
            "south_of_uptown": int(south.sum()),
            "east_north_west_of_uptown": int((~south).sum()),
            "median_km_to_nearest_lynx_station": round(float(top.nearest_station_m.median()) / 1000, 1),
            "within_15min_walk_of_lynx": {
                "any_overlap": int((top.rail15_share > 0).sum()),
                "at_least_10pct": int((top.rail15_share >= 0.10).sum()),
                "at_least_25pct": int((top.rail15_share >= 0.25).sum()),
                "at_least_half": int((top.rail15_share >= 0.50).sum()),
                "residents_estimate": int(round((top.rail15_share * top["pop"]).sum())),
                "residents_estimate_share": round(float((top.rail15_share * top["pop"]).sum() / top["pop"].sum()), 3),
                "note": "residents assumed spread evenly within each NPA",
            },
        },
        "stations_reaching_a_store": {f"{t}_min": stations_reaching(t) for t in WALK_TIMES},
        "stations_total": {l: int((acc.line == l).sum()) for l in ("blue", "gold")},
        "priority_stations": [
            {"line": r.line, "station": r.station, "need": round(r.need, 2),
             "residents_15min": int(round(r.residents_15min)),
             "nearest_store": r.nearest_store, "nearest_store_km": round(r.nearest_store_m / 1000, 1),
             "walkshed_npas": sw[f"{r.line}|{r.station}"]}
            for r in prio.itertuples()],
        "gold_line_need_quintiles": acc[acc.line == "gold"].set_index("station").need_quintile.to_dict(),
    }

    # ---------------- write outputs ----------------
    web = npa.to_crs(CRS_WEB).copy()
    web["geometry"] = npa.geometry.simplify(SIMPLIFY_FT).to_crs(CRS_WEB)
    qol_json = {
        "years": years,
        "npas": [{"id": int(r.npa), "city": r.City, "c": round_geom(r.geometry), "gb": int(r.gb),
                  "rp": [round(r.lon, 5), round(r.lat, 5)],
                  **{k: num(r[k]) for k in QOL_VARS}} for _, r in web.iterrows()],
        "sw": sw,
    }
    (out / "qol_npa_food.json").write_text(json.dumps(qol_json, separators=(",", ":")))

    cols = ["npa", "City", "pop", "hu", "snap", "groc", "gb", "inc", "drive", "transit"] + \
           ["r_" + k for k in NEED] + ["score", "rank", "quintile", "bivariate", "groc15_share",
                                       "rail15_share", "sector", "nearest_station_m"]
    rows_lbl, cols_lbl = ["low", "moderate", "high"], ["many_homes_near", "few_homes_near", "none_within_half_mile"]
    npa["bi_food_assistance"] = npa.bivariate.map(lambda b: rows_lbl[int(b[0])] if isinstance(b, str) else None)
    npa["bi_grocery_access"] = npa.bivariate.map(lambda b: cols_lbl[int(b[1])] if isinstance(b, str) else None)
    cols = [c if c != "bivariate" else "bi_food_assistance" for c in cols]
    cols.insert(cols.index("bi_food_assistance") + 1, "bi_grocery_access")
    npa[cols].rename(columns={"gb": "groc_blank_read_as_0", "pop": "pop_2020", "hu": "housing_units"}) \
        .round(4).to_csv(out / "npa_need.csv", index=False)
    acc.drop(columns=["lon", "lat"]).assign(residents_15min=acc.residents_15min.round()) \
        .round(3).to_csv(out / "station_need.csv", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    if embed:
        html = embed.read_text(encoding="utf-8")
        pat = re.compile(r'(<script id="qol" type="application/json">)(.*?)(</script>)', re.S)
        assert pat.search(html), f'no <script id="qol"> in {embed}'
        html = pat.sub(lambda m: m.group(1) + json.dumps(qol_json, separators=(",", ":")) + m.group(3), html)
        embed.write_text(html, encoding="utf-8")
        print(f"Updated the neighbourhood data in {embed}")

    t = summary["top20_need"]
    print(f"""
Results (equal weights, 15 minute walk, all chains)
  Top-20% need NPAs ............... {t['npas']} NPAs, {t['population']:,} residents (2020)
    no chain grocery within 1/2 mi  {t['no_chain_grocery_within_half_mile']['npas']} NPAs, {t['no_chain_grocery_within_half_mile']['population']:,} residents
    land within 15 min of a store   {t['land_share_within_15min_walk_of_grocery']:.0%} (all populated NPAs: {t['land_share_within_15min_walk_of_grocery_all_populated']:.0%})
    east/north/west vs south ...... {t['east_north_west_of_uptown']} vs {t['south_of_uptown']}
    median distance to LYNX ....... {t['median_km_to_nearest_lynx_station']} km
    at least half within 15 min of a station: {t['within_15min_walk_of_lynx']['at_least_half']} NPAs; est. {t['within_15min_walk_of_lynx']['residents_estimate']:,} residents ({t['within_15min_walk_of_lynx']['residents_estimate_share']:.0%})
  Stations reaching a store ....... {summary['stations_reaching_a_store']}
  Priority stations ............... {[p['station'] for p in summary['priority_stations']]}
Outputs written to {out}""")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--root", type=Path, default=here.parent, help="folder holding qol_data/, Data/ and DataGrocery/")
    ap.add_argument("--out", type=Path, default=here / "analysis_output", help="output folder")
    ap.add_argument("--embed", type=Path, default=None, help="index.html whose <script id=\"qol\"> data to replace")
    a = ap.parse_args()
    run(a.root.resolve(), a.out.resolve(), a.embed)
