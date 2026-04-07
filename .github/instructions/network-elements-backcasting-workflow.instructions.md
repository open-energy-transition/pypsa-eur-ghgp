---
applyTo:
  - "scripts/add_electricity.py"
  - "scripts/add_existing_baseyear.py"
  - "scripts/build_powerplants.py"
  - "scripts/build_electricity_demand.py"
  - "scripts/prepare_network.py"
  - "scripts/base_network.py"
  - "scripts/process_cost_data.py"
  - "config/**/*.yaml"
  - "data/custom_costs.csv"
  - "rules/build_electricity.smk"
  - "rules/solve_myopic.smk"
---

# PyPSA-Eur Network Elements: Workflow, Configuration, and Backcasting Strategy

## Overview

This document provides a rigorous, code-grounded reference for how the four main network element categories — **Load**, **Power Plants**, **Storage**, and **Transmission** — are handled in PyPSA-Eur v2026.02.0 running in **myopic foresight** mode, as configured for the GHGP backcasting project. For each element, the document covers:

- The full Snakemake pipeline (datasets → rules → scripts → output files)
- How configuration settings flow into script logic
- The specific challenges arising when backcasting to a historical year Y ∈ {2020, …, 2025}
- Recommended configuration strategy for correct backcasting (Option B)

### Current test configuration (`config/test/config.rmi.yaml`)

| Parameter | Value |
|---|---|
| `foresight` | `myopic` |
| `scenario.planning_horizons` | `[2025]` |
| `load.fixed_year` | `2024` |
| `electricity.transmission_limit` | `v1.0` |
| `electricity.extendable_carriers` | all `[]` (no expansion) |
| `electricity.powerplants_filter` | `"(DateOut > 2025 or DateOut != DateOut) and (DateIn < 2026 or DateIn != DateIn)"` |
| `sector.electricity_distribution_grid` | `false` |
| countries | `[DE]` |
| snapshots | March 2013, 3H resolution |

### Key architectural fact: planning_horizons[0] controls three things simultaneously

In myopic mode, `scenario.planning_horizons[0]` propagates to:

1. **baseyear** in `add_existing_baseyear.py` → controls which plants are "existing" vs "future"
2. **The IRENASTAT cutoff** → `add_existing_renewables()` includes all annual columns up to `baseyear`
3. **The costs file** → `add_existing_baseyear` reads `costs_{planning_horizons[0]}_processed.csv`

These three dependencies are tightly coupled and cannot be decoupled without modifying core PyPSA-Eur scripts. The single correct lever for backcasting to year Y is therefore `planning_horizons: [Y]`.

---

## 1. Load

### 1.1 Snakemake Workflow

```
[retrieve_electricity_demand_opsd]   → data/opsd/...
[retrieve_electricity_demand_entsoe] → data/entsoe/...
[retrieve_electricity_demand_neso]   → data/neso/...         (UK only)
[retrieve_synthetic_electricity_demand] → data/synthetic/... (gap-filling)
         |
         ▼
rule build_electricity_demand (rules/build_electricity.smk:6)
  script: scripts/build_electricity_demand.py
  output: resources/electricity_demand.csv
         |
         ▼
rule prepare_sector_network / rule add_electricity
  → load attached to network buses via attach_load()
```

**Data sources** (all merged in `build_electricity_demand.py`):
- **OPSD** (Open Power System Data): primary historical demand for continental Europe
- **ENTSO-E SFTP**: hourly actual load per country from ENTSO-E
- **NESO**: UK-specific demand (replaces ENTSO-E for GB)
- **Synthetic demand**: fills gaps for countries with missing data (UA, MD, XK, CY, MT excluded)

### 1.2 Key Configuration Settings

```yaml
# config/config.default.yaml
load:
  fixed_year: false         # ← false means no override; demand follows simulation year
  manual_adjustments: true  # country-specific manual corrections
  scaling_factor: 1.0       # uniform scaling applied after loading
  fill_gaps:
    enable: true
    interpolate_limit: 3    # hours; gaps smaller than this are linearly interpolated
    time_shift_for_large_gaps: "1Y"  # larger gaps filled by copying same period ±1 year
  supplement_synthetic: true
```

**How `fixed_year` works** (script lines 328-336):

```python
fixed_year = snakemake.params["load"].get("fixed_year", False)
if fixed_year:
    fixed_year_index = snapshots.map(lambda t: t.replace(year=int(fixed_year)))
    load = load.loc[fixed_year_index]
    load.index = snapshots
```

The model runs with snapshots anchored to a simulation year (e.g., `snapshots.start: "2013-03-01"`) but the **demand values** are taken from `fixed_year`. Each snapshot timestamp `t` has its year component replaced by `fixed_year`, then the corresponding row from the historical demand CSV is selected. The result is that the temporal pattern of the 2013 snapshots is preserved (day of week, length) while the demand magnitudes come from year `fixed_year`.

**Edge case**: if `fixed_year` is a leap year and the simulation period doesn't include Feb 29, no error occurs because the mapping is done per-snapshot, not per-day.

### 1.3 Backcasting Recommendation

For backcasting to year Y, set:
```yaml
load:
  fixed_year: Y
```

This is the only change needed for load. The snapshot structure (months, resolution) remains unchanged; only the demand levels change to reflect year Y.

---

## 2. Power Plants

### 2.1 Data Sources

| Source | Content | Usage |
|---|---|---|
| **PowerPlantMatching (PPM)** | Conventional generators (coal, lignite, gas OCGT/CCGT, nuclear, oil, biomass), PHS, hydro reservoir, run-of-river | All foresight modes |
| **IRENASTAT** (via `powerplantmatching`) | Annual installed capacity: solar PV, onshore wind, offshore wind | Myopic mode only (exclusively) |
| **Custom powerplants** | `data/custom_powerplants.csv` | Supplement or override PPM entries |
| **Hydro capacities** | `data/hydro_capacities.csv` | PHS/reservoir capacity bounds |
| **atlite profiles** | `resources/profile_{clusters}_{carrier}.nc` | Renewable capacity factors and p_nom_max per bus |

### 2.2 Overnight Mode Pipeline

In `foresight: overnight`, the full pipeline is:

```
rule retrieve_powerplants
  → raw PPM dataset (cached)

rule build_powerplants (rules/build_electricity.smk:35)
  script: scripts/build_powerplants.py
  params: powerplants_filter, custom_powerplants
  input:  networks/base_s_{clusters}.nc  (for spatial matching)
          powerplants.csv (raw PPM)
  output: resources/powerplants_s_{clusters}.csv  ← FILTERED + SPATIALLY MATCHED

rule add_electricity (rules/build_electricity.smk:790)
  script: scripts/add_electricity.py
  input:  powerplants_s_{clusters}.csv
          costs_{costs.year}_processed.csv          ← uses costs.year (NOT planning_horizons)
  calls:
    attach_conventional_generators()  [line 587]
    attach_hydro()                    [line 747]
    attach_wind_and_solar()           [line 468]  → p_nom from estimate_renewable_capacities
    attach_existing_batteries()       [line 710]  → only if estimate_battery_capacities: true
    attach_storageunits()             [line 1039] → only if extendable_carriers.StorageUnit ≠ []
    attach_stores()                   [line 1104] → only if extendable_carriers.Store ≠ []
  output: resources/networks/base_s_{clusters}_elec.nc
```

In overnight mode, the `estimate_renewable_capacities` block is active. It sets `p_nom` for renewable generators using either:
- PPM (`from_powerplantmatching: true`): aggregated installed capacity from the PPM database for `year`
- IRENASTAT (`from_irenastat: true`): cumulative installed capacity from IRENASTAT for `year`

```yaml
# config/config.default.yaml
electricity:
  estimate_renewable_capacities:
    enable: true
    from_powerplantmatching: true   # uses PPM aggregated capacity
    from_irenastat: false           # uses IRENASTAT (overrides PPM if true)
    year: 2024                      # which year's cumulative capacity to use
```

### 2.3 Myopic Mode Pipeline

**Critical difference from overnight**: the `estimate_renewable_capacities` block is **entirely skipped**. The log message at lines 1301-1320 of `add_electricity.py` reads:

> `"Skipping renewable capacity estimation because they are added later in rule add_existing_baseyear with foresight mode 'myopic'."`

All settings under `electricity.estimate_renewable_capacities` (including `from_powerplantmatching`, `from_irenastat`, `year`) are **irrelevant in myopic mode**. Renewable capacities are exclusively sourced from IRENASTAT via `add_existing_baseyear.py`.

```
rule retrieve_powerplants
rule build_powerplants            → resources/powerplants_s_{clusters}.csv
rule add_electricity              → resources/networks/base_s_{clusters}_elec.nc
                                    (wind/solar added with p_nom=0; structure only)
         |
         ▼
rule add_existing_baseyear (rules/solve_myopic.smk:6)
  ONLY RUNS FOR planning_horizons[0]
  (wildcard_constraints: planning_horizons = config["scenario"]["planning_horizons"][0])
  
  script: scripts/add_existing_baseyear.py
  params:
    baseyear   ← config["scenario"]["planning_horizons"][0]
    grouping_years_power ← config["existing_capacities"]["grouping_years_power"]
    carriers   ← config["electricity"]["renewable_carriers"]
  input:
    powerplants_s_{clusters}.csv        (already filtered by powerplants_filter)
    costs_{planning_horizons[0]}_processed.csv
  output: resources/networks/base_s_{clusters}_..._brownfield.nc
```

### 2.4 The `powerplants_filter` Mechanism

**Location**: `scripts/build_powerplants.py`, lines 239-241.

```python
ppl_query = snakemake.params.powerplants_filter
if isinstance(ppl_query, str):
    ppl.query(ppl_query, inplace=True)
```

`powerplants_filter` is a **pandas `.query()` string** evaluated against the raw PPM DataFrame. It is applied exactly **once**, at the `build_powerplants` stage. The resulting `powerplants_s_{clusters}.csv` is then reused by:
- `add_electricity.py` (via `attach_conventional_generators`, `attach_hydro`)
- `add_existing_baseyear.py` (via `add_power_capacities_installed_before_baseyear`)

**Available PPM columns for filtering** (selected):

| Column | Type | Example |
|---|---|---|
| `DateIn` | float (year) | `2003`, `NaN` |
| `DateOut` | float (year) | `2030`, `NaN` |
| `Country` | str (alpha-2) | `"DE"`, `"FR"` |
| `Fueltype` | str | `"Hard Coal"`, `"Nuclear"`, `"Natural Gas"` |
| `Technology` | str | `"CCGT"`, `"Steam Turbine"`, `"Pumped Storage"` |
| `Capacity` | float (MW) | `800.0` |

**NaN handling idiom**: `DateOut != DateOut` is the pandas `.query()` idiom for `DateOut.isna()`. Plants with no retirement date should be kept (they are still operating), so the correct filter is:

```yaml
powerplants_filter: "(DateOut > Y or DateOut != DateOut) and (DateIn < Y+1 or DateIn != DateIn)"
```

This keeps plants where:
- `DateOut > Y` (not yet retired at year Y), **or** `DateOut` is NaN (no known retirement date)
- `DateIn < Y+1` (commissioned by end of year Y), **or** `DateIn` is NaN (no known commissioning date)

**Scope limitation**: `powerplants_filter` applies only to PPM-sourced conventional generators, PHS, and hydro. It does **not** apply to IRENASTAT renewables.

### 2.5 `add_power_capacities_installed_before_baseyear()`

This function processes the filtered PPM CSV for use in the brownfield network. Key steps:

1. **Drop non-conventional fueltypes** explicitly:
   ```python
   fueltype_to_drop = ["Hydro", "Wind", "Solar", "Geothermal", "Waste",
                       "Other", "CCGT, Thermal", "Battery", "Heat Storage"]
   technology_to_drop = ["Pv", "Storage Technologies"]
   ```
   Hydro and renewables are dropped because they are added separately (PHS/hydro by `attach_hydro()` in add_electricity, renewables by `add_existing_renewables()`).

2. **Fill missing dates**:
   - `DateIn`: filled with mean `DateIn` per fueltype group; rows still missing are dropped
   - `DateOut`: estimated as `DateIn + technology_lifetime` from the costs table if missing

3. **Merge renewables** (via `add_existing_renewables()` — see Section 2.6)

4. **Drop phased-out plants**: `df_agg[df_agg["DateOut"] < baseyear]` are removed

5. **Drop plants with `DateIn > max(grouping_years)`**: emits warning; these are lost

6. **Assign `grouping_year`**:
   ```python
   df_agg["grouping_year"] = pd.cut(
       df_agg.DateIn,
       bins=grouping_years,
       labels=grouping_years[1:],   # right-closed bins; label = right edge
       right=True,
       include_lowest=True,
   ).astype(int)
   ```

7. **Compute adjusted lifetime**:
   ```python
   df_agg["lifetime"] = df_agg.DateOut - df_agg["grouping_year"] + 1
   ```

### 2.6 The `grouping_years_power` Problem

**Default value** (`config/config.default.yaml`):
```yaml
existing_capacities:
  grouping_years_power:
  - 1900
  - 1950
  - 1955
  - 1960
  # ... (5-year bins) ...
  - 2020
  - 2025
  - 2030
```

The bins are `[..., 2020, 2025, 2030]`. For any plant whose `DateIn` falls in the range (2020, 2025], `pd.cut` assigns `grouping_year = 2025`. If `baseyear = 2024` and a plant has `DateOut = 2024`:

```
lifetime = DateOut - grouping_year + 1 = 2024 - 2025 + 1 = 0
```

A lifetime of 0 causes a division-by-zero in the annuity calculation. Even a lifetime of 1 year is physically wrong for a plant built in 2023 that retires in 2024.

**Fix**: insert the backcasting year Y into `grouping_years_power` between its two neighboring bins. For `Y = 2024`:

```yaml
existing_capacities:
  grouping_years_power:
  - 1900
  - 1950
  # ... (omitted for brevity) ...
  - 2020
  - 2024   # ← inserted
  - 2025
  - 2030
```

With this change, plants with `DateIn ∈ (2020, 2024]` get `grouping_year = 2024`, and their lifetime is computed relative to 2024 as expected.

### 2.7 `add_existing_renewables()` — IRENASTAT Source

```python
irena = pm.data.IRENASTAT().powerplant.convert_country_to_alpha2()
irena = irena.query("Country in @countries")
irena = irena.groupby(["Technology", "Country", "Year"]).Capacity.sum()
```

This call is **unconditional** — there is no configuration switch to disable it or change the data source. The IRENASTAT table has one column per year (e.g., 2000, 2001, …, 2025). The function uses **all columns up to `baseyear` = `planning_horizons[0]`**.

For each renewable carrier (solar, onwind, offwind-ac) and each country:
1. Year-over-year differences are computed (annual capacity additions)
2. Additions are distributed among bus-level generators proportional to `p_nom_max`
3. Each annual vintage creates a row in `df_agg` with:
   - `DateIn = year`, `DateOut = year + lifetime - 1`
   - `Capacity` = annual addition at that bus

**The IRENASTAT cutoff consequence**:

| `planning_horizons[0]` | IRENASTAT includes | DE solar capacity example |
|---|---|---|
| `2025` | columns up to and including 2025 | ~10 GW of 2025 additions included → **wrong for a 2024 backcast** |
| `2024` | columns up to and including 2024 | correct snapshot of 2024 end-of-year installed capacity |
| `2023` | columns up to and including 2023 | correct snapshot of 2023 end-of-year installed capacity |

Because IRENASTAT provides cumulative data (cumulative installation per country per year), using `baseyear = 2025` for a 2024 model overstates renewable capacity by ~one full year of additions.

---

## 3. Storage

### 3.1 PHS and Hydro Reservoir

**Data source**: PowerPlantMatching (PPM), same pipeline as conventional generators.

**Snakemake path**:
```
build_powerplants → powerplants_s_{clusters}.csv
         |
         ▼
add_electricity → attach_hydro() [line 747 in add_electricity.py]
```

`attach_hydro()` reads the filtered `powerplants_s_{clusters}.csv` and adds:
- **Run-of-River (ror)** → `Generator` with carrier `"ror"`, `p_nom` from PPM capacity
- **Hydro reservoir** → `StorageUnit` with carrier `"hydro"`, capacity from `data/hydro_capacities.csv`
- **PHS (Pumped Hydro Storage)** → `StorageUnit` with carrier `"PHS"`, `p_nom` from PPM capacity

`powerplants_filter` applies to these because they come from the same PPM CSV. A filter like `(DateOut > Y or DateOut != DateOut) and (DateIn < Y+1 or DateIn != DateIn)` will correctly exclude PHS plants not yet built or already decommissioned at year Y.

**In `add_existing_baseyear.py`**: `"Hydro"` fueltype is explicitly dropped from `df_agg` (line 207-219). This means `add_existing_baseyear` does **not** modify or override the PHS/hydro capacities set by `attach_hydro()`.

### 3.2 Existing Batteries (PPM)

```yaml
# config/config.default.yaml
electricity:
  estimate_battery_capacities: false   # ← default
```

If `estimate_battery_capacities: true`, `add_electricity.py` calls `attach_existing_batteries()`, which reads battery entries from `powerplants_s_{clusters}.csv` (PPM data). PPM battery coverage is sparse and incomplete for the 2020-2025 period.

In `add_existing_baseyear.py`, `"Battery"` fueltype is explicitly dropped from `df_agg`, so even if batteries were added via `attach_existing_batteries()`, they would not be overridden.

### 3.3 Extendable Storage (StorageUnit and Store)

```yaml
# config/config.default.yaml
electricity:
  extendable_carriers:
    Generator:
    - solar
    - "solar-hsat"
    - onwind
    - "offwind-ac"
    - "offwind-dc"
    - "offwind-float"
    - OCGT
    - CCGT
    StorageUnit: []
    Store:
    - battery
    - H2
    Link: []
```

In `add_electricity.py`:
- `attach_storageunits()` (line 1039): adds extendable `StorageUnit` components — skipped because `extendable_carriers.StorageUnit: []` by default
- `attach_stores()` (line 1104): adds extendable `Store` components — by default `battery` and `H2` stores are extendable

For backcasting (dispatch optimization, no capacity expansion), all `extendable_carriers` lists should be set to `[]` — see Section 5.

### 3.4 Backcasting Recommendations for Storage

PHS and hydro follow the `powerplants_filter` logic:
- Set `powerplants_filter` appropriately for year Y (see Section 4.3)
- No additional changes needed for storage

Battery and extendable storage: remain disabled (current configuration is correct for backcasting).

---

## 4. Transmission and Distribution Lines

### 4.1 HV Transmission Network (OSM)

**data source**: OSM archive dataset version `v0.7`, retrieved from Zenodo record 18619025. The data was retrieved from the OpenStreetMap Overpass API on **11 February 2026**.

**CSV files** (in `data/osm/build/` or the Zenodo archive folder):
- `lines.csv`: AC overhead/underground lines
- `links.csv`: DC links
- `buses.csv`: substations and interconnection nodes
- `transformers.csv`: voltage transformers
- `converters.csv`: AC/DC converters

**Voltage selection**: controlled by `electricity.voltages` (default: `[220., 300., 380., 500., 600., 750.]`). Only lines in this voltage range are included.

**Important limitation**: the OSM dataset has **no `DateIn` or `DateOut` columns**. It is a topological snapshot of the transmission network as it existed in early 2026. There is no mechanism in PyPSA-Eur to automatically select a historical year's network topology.

**Under-construction lines**: the `under_construction` boolean column in `lines.csv` flags lines that were under construction at the time of the OSM snapshot. This is handled by `base_network.py` → `_adjust_capacities_of_under_construction_branches()` based on the `lines.under_construction` config setting.

**Snakemake path**:
```
data/osm/archive/v0.7/{lines,links,buses,...}.csv   (Zenodo download)
         |
         ▼
rule base_network (rules/build_electricity.smk:~100)
  script: scripts/base_network.py
  calls: _adjust_capacities_of_under_construction_branches()
  output: resources/networks/base.nc

rule cluster_network / rule simplify_network
  → resources/networks/base_s_{clusters}.nc

rule add_electricity
  → sets line capital costs (not s_nom)

rule prepare_network (rules/build_electricity.smk:841)
  script: scripts/prepare_network.py
  params: transmission_limit
  calls:  set_transmission_limit()
  → controls whether lines are s_nom_extendable
```

### 4.2 Under-Construction Lines

Config setting: `lines.under_construction` (and `links.under_construction`).

| Value | Effect on flagged lines |
|---|---|
| `"keep"` | Kept in network with their original `s_nom` → line is treated as operational |
| `"zero"` | Kept in network topology with `s_nom = 0` → line exists but carries no power |
| `"remove"` | Removed from network entirely → bus may become isolated if no other connection |

For backcasting to historical years, the recommended setting is **`"zero"`**. Lines under construction in Feb 2026 may or may not have been in service in earlier years. Setting their `s_nom = 0` preserves the bus topology (preventing islands) while conservatively assuming they were not yet contributing capacity.

### 4.3 Transmission Expansion Control

**In `prepare_network.py`** (lines 357-359):

```python
kind = snakemake.params.transmission_limit[0]    # first character: "v" or "c"
factor = snakemake.params.transmission_limit[1:]  # remainder: "1.0", "opt", "1.25"
set_transmission_limit(n, kind, factor, costs, Nyears)
```

**In `set_transmission_limit()`** (lines 159-194):

```python
if factor == "opt" or float(factor) > 1.0:
    n.lines["s_nom_extendable"] = True      # lines become investment variables
    n.links.loc[links_dc_b, "p_nom_extendable"] = True
```

| `transmission_limit` | `kind` | `factor` | `float(factor) > 1.0` | `s_nom_extendable` |
|---|---|---|---|---|
| `v1.0` | `"v"` | `"1.0"` | `False` | `False` → **no expansion** |
| `vopt` | `"v"` | `"opt"` | (special case) | `True` → **fully extendable** |
| `v1.25` | `"v"` | `"1.25"` | `True` | `True` + 25% volume cap |
| `c1.0` | `"c"` | `"1.0"` | `False` | `False` → **no expansion** |

The default setting `transmission_limit: vopt` results in `s_nom_extendable = True` — lines become investment variables optimised freely. Setting `factor = "1.0"` (i.e., `v1.0`) makes `float("1.0") > 1.0` evaluate to `False`, so no line is made extendable and a `GlobalConstraint` fixing total transmission volume is added. For backcasting (no expansion), `v1.0` or `c1.0` should be used — see Section 5.

### 4.4 Transmission Projects (TYNDP)

**Rule**: `add_transmission_projects_and_dlr` in `build_electricity.smk`
**Sources**: TYNDP2020, NEP, manually defined projects

Relevant config:
```yaml
transmission_projects:
  enable: false        # ← disabled by default; enable to include planned projects
  status:
    - "under_consideration"
    - "planned"
    - "confirmed"
  new_link_capacity: zero  # new HVDC links added with p_nom=0 (infrastructure exists, no flow)
```

When enabled, new lines/links from TYNDP are added to the network. With `new_link_capacity: zero`, HVDC links are given `p_nom = 0` (present topologically but carry no power unless made extendable).

For backcasting, `transmission_projects.enable: false` is appropriate unless you want to explicitly include planned projects that were confirmed in the target year.

### 4.5 Electricity Distribution Grid

```yaml
sector:
  electricity_distribution_grid: true   # ← enabled by default
```

The distribution grid is a virtual component (a resistanceless Link between HV and LV buses) added in `prepare_sector_network.py` → `insert_electricity_distribution_grid()`. By default it is enabled. When set to `false`, this function is not called. For electricity-only runs without sector coupling, distribution grid representation is not needed and it should be disabled — see Section 5.

### 4.6 Backcasting Recommendations for Transmission

The OSM snapshot is a 2026 static map — no automated historical network selection exists. The recommended approach:

1. **`lines.under_construction: zero`** — prevents UC lines from contributing capacity without removing them from topology
2. **`transmission_limit: v1.0`** — keeps all lines at fixed `s_nom`, no expansion (current setting is correct)
3. **`transmission_projects.enable: false`** — do not add future TYNDP projects that were not yet built at year Y
4. Accept that topology will reflect a 2026 snapshot; for the GHGP project this is acceptable since major grid topology changes between 2020 and 2025 are small relative to model resolution

---

## 5. Technology Costs and Fuel Prices

### 5.1 Snakemake Workflow

```
data/costs/archive/v0.14.0/costs_{Y}.csv   ← raw technology cost assumptions
data/custom_costs.csv                        ← project-specific overrides (path: costs.custom_cost_fn)
         |
         ▼
rule process_cost_data (rules/build_electricity.smk:632)
  script: scripts/process_cost_data.py
  output: resources/{RDIR}/costs_{Y}_processed.csv
```

`process_cost_data.py` reads the raw cost CSV and `custom_costs.csv`, applies overrides, computes derived quantities (`capital_cost` as annualised investment, `marginal_cost = VOM + fuel/efficiency`), and writes a processed CSV. The gas fuel price is auto-propagated to OCGT and CCGT generators inside the script.

The processed file `costs_{Y}_processed.csv` is consumed by:
- `add_electricity.py`: `marginal_cost`, `capital_cost`, `efficiency` for all generators, hydro, and storage
- `add_existing_baseyear.py`: `lifetime`, `capital_cost` for existing plant groupings
- `prepare_network.py`: transmission capital costs

### 5.2 Custom Cost Overrides (`custom_costs.csv`)

`data/custom_costs.csv` allows parameter overrides per technology and planning horizon without modifying the raw cost files. Each row specifies `planning_horizon`, `technology`, `parameter`, and `value`. Rows with `planning_horizon=all` apply to every year; rows with a specific year (e.g. `2024`) apply only to that wildcard.

Overrides fall into two categories:
- **Raw attributes** (`fuel`, `efficiency`, `investment`, `lifetime`, `FOM`, `VOM`): applied before `marginal_cost` and `capital_cost` are computed — the correct way to set fuel prices.
- **Prepared attributes** (`marginal_cost`, `capital_cost`): applied after computation, directly overriding the derived values.

### 5.3 Conventional Generator Fuel Prices: `dynamic_fuel_price`

```yaml
conventional:
  dynamic_fuel_price: false   # ← default used for GHGP project
```

- **`false`**: each generator gets a static `marginal_cost` from `costs_{Y}_processed.csv`. Fuel prices are set once per year via `custom_costs.csv`.
- **`true`**: requires `resources/monthly_fuel_price.csv` (built from World Bank CMO Excel by `build_fossil_fuel_prices` rule); `add_electricity.py` assigns an hourly `marginal_cost` per snapshot.

For the GHGP project `dynamic_fuel_price: false` is correct: snapshots use 2013 climate data mapped to year-Y demand levels, so a static annual-average fuel price is consistent with this approximation.

### 5.4 Backcasting Recommendations for Technology Costs and Fuel Prices

For backcasting to year Y, the key cost-side change is to use **historically correct fossil fuel import prices** for that year. Gas, coal, and oil prices varied significantly across 2020–2025 (notably the 2021–2022 gas price spike), and using default or future-year values would distort the dispatch of conventional generators.

The recommended approach is:
1. For each backcasting year Y, add a fuel price override row in `data/custom_costs.csv` for `technology=gas` (OCGT and CCGT inherit the gas price automatically), `technology=coal`, and `technology=oil`.
2. Keep `conventional.dynamic_fuel_price: false` — annual-average prices are sufficient given the snapshot structure.
3. All other cost parameters (capital costs, efficiency, lifetimes) can remain as in a reference case (e.g., `costs_2025.csv`), since the model is dispatch-only and these only affect annuity calculations used for plant groupings.

---

## 6. Backcasting Implementation Strategy

### 6.1 Core Principle

For backcasting to year Y, **`scenario.planning_horizons: [Y]`** must match the target year. This single parameter change propagates to:
- `baseyear = Y` in `add_existing_baseyear.py`
- IRENASTAT data clipped at year Y
- Cost file: `costs_Y_processed.csv` (must exist)

All other changes listed below follow from this primary constraint.

### 6.2 Required Configuration Changes per Year Y

```yaml
# Required changes in config/test/config.rmi.yaml (or per-year scenario file)

scenario:
  planning_horizons:
  - Y                    # ← 1. primary control (baseyear, IRENASTAT cutoff, cost file)

load:
  fixed_year: Y          # ← 2. demand data from year Y

costs:
  year: Y                # ← 3. technology costs for year Y (used by add_electricity)

electricity:
  powerplants_filter: "(DateOut > Y or DateOut != DateOut) and (DateIn < Y+1 or DateIn != DateIn)"
  # ← 4. keep plants operating in year Y from PPM
  # Note: "DateOut != DateOut" is the pandas .query() idiom for DateOut.isna()

existing_capacities:
  grouping_years_power:
  - 1900
  - 1950
  - 1955
  - 1960
  - 1965
  - 1970
  - 1975
  - 1980
  - 1985
  - 1990
  - 1995
  - 2000
  - 2005
  - 2010
  - 2015
  - 2020
  - Y          # ← 5. insert Y here if Y ∉ {2025, 2030} to avoid grouping_year > Y edge cases
  - 2025
  - 2030
  # (skip the "- Y" line if Y = 2025, since 2025 is already in the list)

biomass:
  share_unsustainable_use_retained:
    Y: <value>   # ← 6. required for non-milestone years only (i.e., Y ∉ {2020, 2025, 2030, 2035, 2040, 2045, 2050})
  share_sustainable_potential_available:
    Y: <value>   # ← 7. required for non-milestone years only
  # IMPORTANT: dict merge preserves all existing default keys — only the new key Y is added.
  # Root cause: build_biomass_potentials.py calls .get(investment_year) on a plain Python dict
  # (not _helpers.get()), which returns None for missing keys → TypeError crash in .mul(None).
  # All other year-keyed config dicts in prepare_sector_network.py use _helpers.get() which
  # interpolates automatically — only the biomass share dicts have this unsafe direct lookup.
  #
  # Values for the GHGP project backcasting years 2020–2025:
  #   Y=2020, 2025: already in config.default.yaml — no override needed
  #   Y=2021, 2022, 2023, 2024: share_unsustainable_use_retained=1, share_sustainable_potential_available=0
  #   (constant between the 2020 and 2025 milestone values, which are both 1 and 0 respectively)
```

The following settings are **one-time overrides from `config.default.yaml`**, constant across all backcasting years. Set them once in the base config file, not per-scenario:

```yaml
# One-time overrides from config.default.yaml (constant across all backcasting years):

electricity:
  extendable_carriers:
    Generator: []      # ← 6a. no capacity expansion for generators (default: [solar, onwind, OCGT, CCGT, ...])
    StorageUnit: []    #        already default
    Store: []          # ← 6b. no extendable stores (default: [battery, H2])
    Link: []           #        already default
  estimate_battery_capacities: false  # ← 7. no PPM batteries (already default; explicit for clarity)
  transmission_limit: v1.0            # ← 8. fix transmission at existing capacity (default: vopt)

lines:
  under_construction: zero     # ← 9. UC lines in topology but s_nom=0 (default: keep)

transmission_projects:
  enable: false                # ← 10. exclude future TYNDP projects (default: true)

sector:
  electricity_distribution_grid: false  # ← 11. electricity-only model, no distribution grid (default: true)
```

### 6.3 Cost File and Fuel Price Strategy

**Cost file requirement**: `add_electricity` reads `costs_{costs.year}_processed.csv` and `add_existing_baseyear` reads `costs_{planning_horizons[0]}_processed.csv`. Both must point to a valid processed cost file.

The upstream `technology-data` v0.14.0 repository provides cost files only for milestone years at 5-year intervals: `costs_2020.csv`, `costs_2025.csv`, `costs_2030.csv`, …, `costs_2050.csv`. Intermediate years (2021, 2022, 2023, 2024) do not exist in the archive and must be created manually.

**Solution**: copy the nearest milestone year (`costs_2025.csv`) to `costs_Y.csv` for each required intermediate year Y. For the GHGP project (dispatch-only, no capacity expansion), cost assumptions primarily affect `marginal_cost` calculations and `efficiency` values. Since conventional generator efficiencies do not vary significantly between 2020 and 2025, this approximation is acceptable. Fuel prices — which vary substantially — are corrected via `custom_costs.csv` overrides.

**Fuel price backcasting strategy**: The `marginal_cost` of conventional generators (gas OCGT/CCGT, coal, lignite, oil, biomass) depends critically on `fuel` prices, which vary significantly across years 2020–2025 (e.g., the European gas price spike in 2021–2022). Since `dynamic_fuel_price: false` is used, a single annual-average fuel price for year Y must be set.

The recommended approach is to override the `fuel` parameter in `data/custom_costs.csv` for each backcasting year. This is a **raw attribute** override (Stage 1 in `process_cost_data.py`), so the correct `marginal_cost = VOM + fuel/efficiency` is automatically recomputed:

```csv
planning_horizon,technology,parameter,value,unit,source,further description
2020,gas,fuel,5.0,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2021,gas,fuel,13.5,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2022,gas,fuel,34.0,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2023,gas,fuel,15.0,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2024,gas,fuel,9.5,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2025,gas,fuel,9.0,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2020,coal,fuel,2.5,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2021,coal,fuel,3.8,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2022,coal,fuel,8.5,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2023,coal,fuel,4.5,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2024,coal,fuel,3.5,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2025,coal,fuel,3.0,EUR/MWh_th,World Bank CMO annual average (EUR2020),
2020,oil,fuel,26.0,EUR/MWh,World Bank CMO annual average (EUR2020),
2021,oil,fuel,32.0,EUR/MWh,World Bank CMO annual average (EUR2020),
2022,oil,fuel,50.0,EUR/MWh,World Bank CMO annual average (EUR2020),
2023,oil,fuel,42.0,EUR/MWh,World Bank CMO annual average (EUR2020),
2024,oil,fuel,38.0,EUR/MWh,World Bank CMO annual average (EUR2020),
2025,oil,fuel,35.0,EUR/MWh,World Bank CMO annual average (EUR2020),
```

**Key rules**:
1. For `technology=gas`: OCGT and CCGT inherit the price automatically via `costs.at["OCGT", "fuel"] = costs.at["gas", "fuel"]` (lines 178-179 of `process_cost_data.py`). Do not add explicit OCGT/CCGT rows — they would be overwritten. For `technology=coal` and `technology=oil`: there is no auto-propagation, so rows must be added directly.
2. `lignite` is domestic (not in World Bank CMO) — use a fixed assumption (~1–3 EUR/MWh_th) with `planning_horizon=all`.
3. Values above are **indicative** — verify against World Bank CMO data (`build_fossil_fuel_prices` rule output: `resources/monthly_fuel_price.csv`) or Eurostat energy statistics.
4. The `planning_horizon` column must be a **string** matching `str(snakemake.wildcards.planning_horizons)`. The CSV is read with `dtype={"planning_horizon": "str"}`, so integer values like `2024` in the CSV are correctly matched.

### 6.4 Rules Requiring Changes

No Snakemake rules require code modification. The `add_existing_baseyear` rule's wildcard constraint:

```python
# rules/solve_myopic.smk
wildcard_constraints:
    planning_horizons=config["scenario"]["planning_horizons"][0]
```

automatically restricts the rule to run only for the first (and only) planning horizon. With `planning_horizons: [Y]`, it runs exclusively for year Y — correct behavior.

### 6.5 Six-Year Backcasting (Multi-Year Automation)

To run all six backcasting years in one workflow:

1. Create a `config/scenarios.yaml` with Snakemake scenario overrides for each year
2. Set `run.scenarios.enable: true` in base config
3. Each scenario overrides `planning_horizons`, `load.fixed_year`, `costs.year`, `powerplants_filter`, and `grouping_years_power` (items 1–5 above). The one-time overrides (items 6–11) should be set in the base config file, not per scenario

The `powerplants_filter` values for each year:

| Year Y | `powerplants_filter` |
|---|---|
| 2020 | `"(DateOut > 2020 or DateOut != DateOut) and (DateIn < 2021 or DateIn != DateIn)"` |
| 2021 | `"(DateOut > 2021 or DateOut != DateOut) and (DateIn < 2022 or DateIn != DateIn)"` |
| 2022 | `"(DateOut > 2022 or DateOut != DateOut) and (DateIn < 2023 or DateIn != DateIn)"` |
| 2023 | `"(DateOut > 2023 or DateOut != DateOut) and (DateIn < 2024 or DateIn != DateIn)"` |
| 2024 | `"(DateOut > 2024 or DateOut != DateOut) and (DateIn < 2025 or DateIn != DateIn)"` |
| 2025 | `"(DateOut > 2025 or DateOut != DateOut) and (DateIn < 2026 or DateIn != DateIn)"` |

### 6.6 What Remains Unchanged Across All Backcasting Years

The following settings from `config.default.yaml` do not need to be overridden at all:

- `foresight: myopic` — fixed for the entire project
- Snapshot structure (`snapshots.start/end`) — simulation always runs over 2013 climate data regardless of the backcasting year
- Number of clusters — spatial resolution kept constant across all years

---

## 7. Cross-Reference: Config → Code Mapping

| Config key | Consuming rule | Script | Line | Effect |
|---|---|---|---|---|
| `scenario.planning_horizons[0]` | `add_existing_baseyear` | `add_existing_baseyear.py` | 792 | Sets `baseyear` → IRENASTAT cutoff, DateOut phaseout threshold, cost file |
| `electricity.powerplants_filter` | `build_powerplants` | `build_powerplants.py` | 239-241 | Filters PPM DataFrame; result propagates to all downstream scripts |
| `electricity.transmission_limit` | `prepare_network` | `prepare_network.py` | 357-359 | Parsed into kind+factor; controls `s_nom_extendable` |
| `load.fixed_year` | `build_electricity_demand` | `build_electricity_demand.py` | 328-336 | Replaces year component of each snapshot timestamp for demand lookup |
| `lines.under_construction` | `base_network` | `base_network.py` | 618 | Handles UC lines: keep/zero/remove |
| `existing_capacities.grouping_years_power` | `add_existing_baseyear` | `add_existing_baseyear.py` | 261-267 | `pd.cut` bins for assigning `grouping_year` to each plant |
| `electricity.extendable_carriers.StorageUnit` | `add_electricity` | `add_electricity.py` | 1039 | Empty list → `attach_storageunits()` adds nothing |
| `electricity.extendable_carriers.Store` | `add_electricity` | `add_electricity.py` | 1104 | Empty list → `attach_stores()` adds nothing |
| `electricity.estimate_battery_capacities` | `add_electricity` | `add_electricity.py` | ~710 | `false` → `attach_existing_batteries()` not called |
| `electricity.estimate_renewable_capacities` | `add_electricity` | `add_electricity.py` | 1301-1320 | **Entirely ignored in myopic mode** (skipped with log message) |
| `sector.electricity_distribution_grid` | `prepare_sector_network` | `prepare_sector_network.py` | — | `false` → `insert_electricity_distribution_grid()` not called |
| `costs.year` | `add_electricity`, `prepare_network` | multiple | — | Cost file year for overnight mode / pre-baseyear rules |
| `conventional.dynamic_fuel_price` | `add_electricity` | `add_electricity.py` | ~1370 | `false` → static marginal_cost from processed CSV; `true` → hourly marginal_cost from `monthly_fuel_price.csv` |
| `custom_costs.csv` `fuel` param | `process_cost_data` | `process_cost_data.py` | 178-183 | Raw attr override: sets `gas.fuel` → auto-propagates to OCGT/CCGT → recomputes `marginal_cost = VOM + fuel/efficiency` |
| `custom_costs.csv` `marginal_cost` param | `process_cost_data` | `process_cost_data.py` | Stage 2 | Prepared attr override: directly sets final `marginal_cost`, bypasses computation |
| `biomass.share_unsustainable_use_retained` | `build_biomass_potentials` | `build_biomass_potentials.py` | 299 | `.get(investment_year)` — returns None for non-milestone years → must add explicit key Y in config |
| `biomass.share_sustainable_potential_available` | `build_biomass_potentials` | `build_biomass_potentials.py` | 327 | `.get(investment_year)` — same unsafe lookup — must add explicit key Y in config |
