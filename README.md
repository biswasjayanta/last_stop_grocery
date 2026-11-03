# Last Stop: Groceries

**Can you walk from a LYNX station to a grocery store, and how many neighbors live within a 5, 10 or 15 minute walk of each store?**

An interactive map of Charlotte, North Carolina, built for the UNC Charlotte GIS Day 2026 **AI Interactive GeoVisualization Competition**. It puts the walking areas around every LYNX Blue Line and Gold Line station on the same map as the walking areas around every grocery store in the city's open data, so you can see where a rail trip ends within reach of food and where it does not.

![Screenshot of the Last Stop: Groceries map](screenshot.png)

**Live map:** `https://<your-github-username>.github.io/<repository-name>/`

---

## The two questions

1. **Rail to groceries.** Step off the train at any LYNX station: is there a grocery store within a 5, 10 or 15 minute walk? Stations that reach a store are marked green in the profile strip; stations that don't are marked with a red ring on the map and a red ✕ in the profile.
2. **Who each store serves on foot.** For every grocery store, how many residents and buildings fall inside its 5, 10 and 15 minute walking area?

At a 15 minute walk with every chain included, **16 of 26 Blue Line stations** and **12 of 17 Gold Line stations** reach a grocery store. Narrow the walk or the chains and the gaps grow quickly.

## What you can do on the map

| Control | What it does |
|---|---|
| **Line** | Switch between the Blue Line and the Gold Line. The other line stays on the map in grey. |
| **Walk time** | Show 5, 10 or 15 minute walks. Changes the map, the profile, the totals and which stations count as reaching a store. |
| **Show** | Turn rail walksheds and grocery walksheds on or off. With both on, grocery walksheds are green fills and rail walksheds are contour lines. |
| **Grocery chains** | Filter by Harris Teeter, Food Lion, Walmart, Aldi, Publix, Target, Compare Foods, The Fresh Market or other grocers. |
| **Walkshed profile** | Each station is a bar placed at its distance along the line, showing residents or buildings within the walk. A strip underneath shows grocery access. |
| **Section handles** | Drag the two handles on the profile to select a stretch of line; the panel totals that section and lists stations with no store in reach. |
| **Hover** | Point at a station or a store for its residents, buildings and what it can reach on foot. Click to zoom in. |
| **Follow map view** | The profile shows only the part of the line visible on the map. |
| **Compass / Align with profile** | Rotate the map by dragging the compass; *Align with profile* turns the line to run left to right like the chart. |

The page works in light and dark mode and on phones.

## Data

| Dataset | Source | Used for |
|---|---|---|
| Grocery stores (161) | City of Charlotte Open Data | Store locations and chain names |
| LYNX rail routes and stations | City of Charlotte Open Data | Blue Line track, Blue and Gold Line stations |
| Building footprints | City of Charlotte Open Data | Building counts within each walkshed |
| Population | WorldPop 2025, 100 m population counts | Residents within each walkshed |

## Method

1. **Walksheds.** 5, 10 and 15 minute walking areas were generated on the street network around each LYNX station and each grocery store. Areas are cumulative: the 15 minute area contains the 10 and 5 minute areas.
2. **Counts.** Building footprints and WorldPop 2025 population cells were summarised inside each walkshed.
3. **Rail-to-grocery access.** A station "reaches" a store within *n* minutes when the station sits inside that store's *n* minute walkshed. This matches what the map shows: a station inside a green area is within that walk of a store.
4. **Distance along the line.** Stations are placed on the profile by their distance along the track.
5. **Section totals** add up the walksheds of the stations in a section. Neighbouring stations' walksheds overlap, so shared blocks are counted once per station.

### Known limitations

- The Gold Line track is drawn stop to stop because no route geometry was available.
- Johnson C. Smith University (Gold Line) has no 15 minute walkshed in the source data.
- One BJ's Wholesale Club has no walkshed in the source data and appears as a point only.
- Population figures are model estimates from a 100 m grid and are rounded for display.

## Run it

The whole map is one self-contained file, `index.html`. All data is embedded in the page, and it loads [D3.js](https://d3js.org/) 7.9.0 from cdnjs, [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/) 3.3.0 from Mapbox, and fonts from Google Fonts.

- **Locally:** open `index.html` in a browser.
- **GitHub Pages:** push `index.html`, `README.md` and `screenshot.png` to a repository, then go to *Settings → Pages*, choose *Deploy from a branch*, select `main` and `/ (root)`, and save. The map appears at `https://<your-github-username>.github.io/<repository-name>/`.

## Basemap (OpenStreetMap)

© OpenStreetMap attribution shown in the bottom-left corner are required by Mapbox's terms; keep them visible.

## Built with

- [D3.js](https://d3js.org/) for projection, zoom, scales and the profile chart
- HTML Canvas for the walkshed overlay
- © OpenStreetMap contributors
- Python (GeoPandas, Shapely) for data preparation
- Typefaces: Archivo, Public Sans and IBM Plex Mono (Google Fonts)

## Author

**Jayanta Biswas**, University of North Carolina at Charlotte
Entry for the UNC Charlotte GIS Day 2026 AI Interactive GeoVisualization Competition.

## Acknowledgment

This map was built with the help of **Claude** (Anthropic), a generative AI assistant, which was used to process the data, design the map and write its code. Analysis choices, data sources and final review are the author's.

## Data credits

City of Charlotte Open Data · WorldPop (www.worldpop.org), 2025 population counts at 100 m resolution · Basemap © Mapbox © OpenStreetMap contributors. Please check each provider's terms before reusing the data.
