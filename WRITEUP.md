# Last Stop: Groceries — write-up

**Jayanta Biswas, UNC Charlotte · GIS Day 2026 AI Interactive GeoVisualization Competition · Topic: Food Security**

## Overview

Which Charlotte neighborhoods have high food need and no grocery store within walking distance, and where could a LYNX station help? *Last Stop: Groceries* answers this on one interactive map. It colors Charlotte's 459 Neighborhood Profile Areas (NPAs) by food need, using data from the Charlotte/Mecklenburg Quality of Life Explorer. On top it draws 5, 10 and 15 minute walking areas (walksheds) around every grocery store and every LYNX Blue Line and Gold Line station. Neighborhoods with high need that are beyond a walk to any store stand out. LYNX stations that serve high-need areas but have no store in reach are flagged as priority sites for a new grocery.

## Data

| Dataset | Source | Year | Use |
|---|---|---|---|
| Neighborhood Profile Areas (459) | Quality of Life Explorer | 2020 boundaries | Neighborhood polygons |
| Residents receiving food assistance (%) | Quality of Life Explorer | 2025 | Need |
| Homes within ½ mile of a chain grocery (%) | Quality of Life Explorer | 2025 | Access |
| Median household income | Quality of Life Explorer | 2024 | Need |
| Workers driving to work alone (%) | Quality of Life Explorer | 2024 | Car access (proxy) |
| Homes within ½ mile of transit (%), population | Quality of Life Explorer | 2025, 2020 | Context |
| Grocery stores (161), LYNX stations (26 Blue, 17 Gold), building footprints | City of Charlotte Open Data | current | Stores, stations, walksheds, counts |
| Population, 100 m grid | WorldPop | 2025 | Residents in each walkshed |

**How the data were managed.** The Quality of Life download (file dated 2 October 2026) was filtered to the latest year of each variable and joined to the NPA polygons. The polygons were simplified to a 40 ft tolerance and reprojected to WGS 84 for the web. In 2025, grocery proximity is blank for 149 NPAs. 81% of those were 0% in 2022, so the blanks were read as 0% and are flagged on the map. Each station walkshed was intersected with the NPAs in NC State Plane feet to find which neighborhoods it covers and in what share. All processing and every figure below are reproduced by `analysis.py` in this folder. It writes the neighborhood data embedded in the page, per-neighborhood and per-station tables, and `summary.json`.

## Method

- **Need × access.** Each NPA is placed on a 3 × 3 grid. Rows are terciles of food assistance (under 8%, 8–24%, 24% and over). Columns are grocery proximity (36% or more of homes within ½ mile, under 36%, or none).
- **Need index.** Food assistance, low income, no grocery nearby and car-light commuting are each ranked across NPAs as percentiles, so that 1 means most need. They are averaged with equal weights; viewers can change the weights on the map. NPAs in the top quintile are *top 20% need*.
- **Priority stations.** A station's need is the area-weighted mean of the index across the NPAs its 15 minute walkshed covers. It is a *priority site* if that score is in the top 20% and no grocery store is within the chosen walk.

## Interpretation

Figures are for equal weights, a 15 minute walk and all grocery chains (`analysis_output/summary.json`).

- **Need is concentrated where stores are not.** The 92 top-20% need NPAs are home to about 198,000 people (2020). In 63 of them, about 120,000 people, no home is within ½ mile of a chain grocery. Only 14% of their land lies within a 15 minute walk of any of the 161 stores.
- **The pattern is an arc.** 76 of the 92 high-need NPAs lie east, north or west of Uptown, and only 16 are to the south. On the map, the darkest *high food assistance, no grocery* class forms a ring around a pale south-central wedge.
- **Rail reaches only a small part of the need.** The median high-need NPA is about 4 km from the nearest LYNX station. Only 6 of the 92 lie at least half within a 15 minute walk of a station. If residents are spread evenly within each NPA, about 14,000 of their 198,000 residents (7%) live within that walk.
- **Where rail can help: Tom Hunter and Old Concord Rd.** These two northeast Blue Line stations are the only ones that both draw on top-20% need neighborhoods and have no grocery within a 15 minute walk. Tom Hunter has about 6,600 residents within a 15 minute walk, and its nearest store is about 2.0 km away in a straight line. Old Concord Rd has about 1,000 residents within a 15 minute walk, its nearest store is about 1.2 km away, and 93% of its walkshed falls in one top-20% need NPA.
- **Rail-to-grocery access thins quickly with walk time.** Within 15 minutes, 16 of 26 Blue Line and 12 of 17 Gold Line stations reach a store. Within 10 minutes that falls to 8 and 4, and within 5 minutes to 3 and 1.
- **The Gold Line has no top-20% station.** French Street, Johnson C. Smith University and Bruns Avenue in the West End are in the next band.

## Summary

Charlotte's food-access gap and its food-need gap overlap: about 120,000 residents live in top-20% need neighborhoods where no home is within ½ mile of a chain grocery. A grocery store at **Tom Hunter** station would serve the most people within walking distance of any priority site, and **Old Concord Rd** is the second candidate. Most high-need neighborhoods lie in the east–north–west arc and are several kilometres from the rail lines. Those areas would need bus links, mobile markets or new stores off the rail lines; a station-area store would not reach them.

## How GeoAI was used

Claude (Anthropic), a generative AI assistant, was used to explore the Quality of Life Explorer's catalog of variables and to write the Python (GeoPandas) code that cleaned, joined and intersected the data. It also computed the need index and the walkshed overlaps, and designed and coded the interactive map (D3, HTML Canvas, MapLibre). The author chose the question, the variables and the weighting approach, and reviewed every result. AI made the work much faster, but it needed checking at each step. For example, the blank grocery values would have silently dropped a third of the neighborhoods. Every figure in this write-up was computed from the data by code that is published with the map (`analysis.py`), not generated.

## Limitations

- Quality of Life Explorer grocery proximity counts chain stores within ½ mile in a straight line. The walksheds use the city's 161-store list and network walking time, so the two measures can disagree.
- Income and commuting are American Community Survey estimates with margins of error, and NPA population is from 2020.
- The need index is relative: it ranks neighborhoods against each other. Changing the weights changes the ranking.
