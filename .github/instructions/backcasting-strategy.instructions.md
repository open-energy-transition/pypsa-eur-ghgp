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

| Parameter | Value | Scope |
|---|---|---|
| `foresight` | `myopic` | constant |
| `scenario.planning_horizons` | `[Y]` (e.g., `[2025]` for baseline) | per-scenario |
| `load.fixed_year` | `Y` (per backcasting year) | per-scenario |
| `costs.year` | `Y` (per backcasting year) | per-scenario |
| `electricity.transmission_limit` | `v1.0` | constant |
| `electricity.extendable_carriers` | all `[]` (no expansion) | constant |
| `electricity.powerplants_filter` | `"(DateOut > Y or DateOut != DateOut) and (DateIn < Y+1 or DateIn != DateIn)"` | per-scenario |
| `lines.under_construction` | `zero` | constant |
| `transmission_projects.enable` | `false` | constant |
| `sector.biomass` | `false` (override; default `true`) | constant |
| `pypsa_eur.Generator` | includes `biomass`, `nuclear` (override; default omits one or both) | constant |
| `sector.methanol.biomass_to_methanol` | `false` (override; default `true`) | constant |
| `sector.methanol.methanol_to_power.ocgt` | `false` (override; default `true`) | constant |
| `sector.hydrogen_underground_storage` | `false` (override; default `true`) | constant |
| `sector.regional_oil_demand` | `false` (override; default `true`) | constant |
| `sector.gas_network` | `false` (override; default `true`) | constant |
| `sector.gas_distribution_grid` | `false` (override; default `true`) | constant |
| `sector.electricity_distribution_grid` | `false` (override; default `true`) | constant |
| `sector.shipping` | `false` (override; default `true`) | constant |
| `sector.aviation` | `false` (override; default `true`) | constant |
| `sector.agriculture` | `false` (override; default `true`) | constant |
| `sector.dac` | `false` (override; default `true`) | constant |
| `sector.co2_network` | `false` (override; default `true`) | constant |
| `sector.co2_spatial` | `false` (override; default `true`) | constant |
| `sector.regional_co2_sequestration_potential.enable` | `false` (override; default `true`) | constant |
| `sector.H2_network` | `false` (override; default `true`) | constant |
| `sector.hydrogen_fuel_cell` | `false` (override; default `true`) | constant |
| `sector.hydrogen_turbine` | `false` (override; default `true`) | constant |
| `sector.SMR` | `false` (override; default `true`) | constant |
| `sector.SMR_cc` | `false` (override; default `true`) | constant |
| `sector.methanation` | `false` (override; default `true`) | constant |
| `sector.transport` | `false` (override; default `true`) | constant |
| `sector.heating` | `false` (override; default `true`) | constant |
| `sector.industry` | `false` (override; default `true`) | constant |
| `sector.biomass` | `false` (override; default `true`) | constant |
| `pypsa_eur.Generator` | includes `biomass`, `nuclear` (override; default omits one or both) | constant |
| `pypsa_eur.Link` | includes only default links | constant |
| `pypsa_eur.StorageUnit` | includes only default storage units | constant |
| `pypsa_eur.Store` | includes only default stores | constant |
| `adjustments.sector.absolute.Link.H2 Electrolysis.p_nom_max` | `0.0` | constant |
| `adjustments.sector.absolute.Store.H2 Store.e_nom_max` | `0.0` | constant |
| `backcasting.project.enable` | `false` (override; default `true`) | constant |
| `backcasting.project.file` | `data/project_generators.csv` | constant |

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

## 5. Electricity-Only Sector Scope

### 5.1 Design Philosophy

PyPSA-Eur in `foresight: myopic` always runs through `prepare_sector_network.py`, which expects a full sector-coupled network. For the GHGP electricity-only model, the strategy is to **disable all demand sectors** (transport, heating, industry, shipping, aviation, agriculture) while retaining the minimal fuel supply infrastructure needed for dispatchable conventional generators.

The correct setting for biomass is **`sector.biomass: false`** — explicitly overriding the `config.default.yaml` default of `true`. With `sector.biomass: true`, `add_biomass()` creates an `"EU solid biomass"` bus and a mandatory-dispatch ENSPRESO Generator, which causes infeasibility in a dispatch model (the bus has committed generation it cannot shed).

Historical biomass powerplants from PPM are preserved as simple AC Generators (carrier `"biomass"`) by adding `biomass` to the `pypsa_eur.Generator` list in `config.rmi.yaml`. This prevents `remove_elec_base_techs()` in `prepare_sector_network.py` from dropping them — which it would do by default, since `biomass` is absent from the default `pypsa_eur.Generator` list.

The four biomass sub-flags (`biomass_boiler`, `biogas_upgrading`, `biomass_to_liquid`, `electrobiofuels`) all reside inside `add_biomass()` (at `prepare_sector_network.py` lines 4288, 4062, 4315, 4370 respectively) and are therefore dead code when `sector.biomass: false`. They do not need to be set. Only the `methanol.*` flags — which live outside `add_biomass()` — require explicit overrides.

### 5.2 Biomass and CHP Configuration

**Pipeline overview** (electricity-only path):

```
scripts/build_powerplants.py (line 236):
  PPM "Solid Biomass" / "Biogas" → renamed to "Bioenergy" fueltype
         |
         ▼
scripts/add_electricity.py (line 284):
  "bioenergy" → adds Generator with carrier="biomass"
         |
         ▼
scripts/prepare_sector_network.py:
  remove_elec_base_techs() (line 656):
    checks pypsa_eur.Generator list → "biomass" is included → Generators kept
  add_biomass() NOT called (sector.biomass: false):
    → no "EU solid biomass" bus created
    → no ENSPRESO mandatory-dispatch Generator added
    → no infeasibility risk
         |
         ▼
  PPM biomass Generators dispatch freely as simple AC electricity Generators
```

**Biomass sub-flags**: `biomass_boiler`, `biogas_upgrading`, `biomass_to_liquid`, and `electrobiofuels` all reside inside `add_biomass()` (at `prepare_sector_network.py` lines 4288, 4062, 4315, 4370 respectively). With `sector.biomass: false`, `add_biomass()` is never called, so these four flags are dead code and do **not** need to be set.

Only the `methanol.*` flags live outside `add_biomass()` and still require explicit overrides:

| Flag | Default | Behaviour if `true` | Required override |
|---|---|---|---|
| `methanol.biomass_to_methanol` | `true` | Adds methanol production Links with investment variables (outside `add_biomass()`) | `false` |
| `methanol.methanol_to_power.ocgt` | `true` | Adds OCGT methanol-to-power Link with `p_nom_extendable=True` (outside `add_biomass()`) | `false` |

### 5.3 Biomass Generators as Simple AC Generators

With `sector.biomass: false` and `biomass` included in the `pypsa_eur.Generator` list, historical biomass powerplants from PPM operate as **simple AC Generators** (not CHP Links). This is the correct representation for the electricity-only backcasting model:

- `p_nom` is taken directly from PPM capacity data
- Marginal cost is computed from the biomass fuel price in `costs_{Y}_processed.csv`
- No heat bus is needed; no efficiency penalty from CHP co-production assumptions

**Important**: in the original PyPSA-Eur code, `add_existing_baseyear.py` added `"urban central solid biomass CHP"` Links **unconditionally**, even when `sector.biomass: false`. It silently created phantom `"<node> solid biomass"` buses and left them with no supply, resulting in two simultaneous bugs:
1. **Double-counting** of capacity and dispatch (both Generators and Links representing the same plants).
2. **Free fuel** (the phantom bus had no energy balance constraint, so biomass fuel cost was zero).

This has been fixed in the GHGP codebase (see `pypsa-eur-code-modifications.instructions.md` §3): a guard in `add_power_capacities_installed_before_baseyear()` skips the biomass CHP Links when `options["biomass"]` is `False`. Biomass plants are therefore represented exclusively as the PPM Generators, symmetrically to other conventional technologies.

### 5.4 Nuclear — double-representation in myopic mode

Nuclear powerplants follow the **same two-pipeline problem** as biomass, but for a different structural reason.

**Pipeline**:
```
scripts/add_electricity.py (attach_conventional_generators):
  PPM "Nuclear" → Generator, carrier="nuclear",
                  p_nom [MW_el], marginal_cost from PPM (fuel+VOM included)

scripts/add_existing_baseyear.py (add_power_capacities_installed_before_baseyear):
  same PPM plants → Link, carrier="nuclear",
                    p_nom [MW_fuel], bus0="EU uranium"
```

The `"EU uranium"` bus is created by `prepare_sector_network.py` → `add_carrier_buses()`, but **without** an energy supply `Generator`:

```python
fossils = ["coal", "gas", "oil", "lignite"]   # uranium is NOT here
# → "EU uranium" bus gets only a Store(e_cyclic=True), no inflow Generator
```

Because the uranium `Store` is `e_cyclic=True` with no inflow, its stored energy is forced to zero at all times. Every nuclear Link is therefore permanently idle (`p0 ≈ 0`). The PPM Generator is the only feasible path and dispatches normally.

**Observed impact** (FR 2030, 39 clusters):
- Generator `p_nom_opt = 52,240 MW`, avg dispatch = 29,487 MW ✅
- Link `p_nom_el = 48,620 MW`, avg dispatch ≈ 10⁻⁸ MW (numerical noise) ❌
- Installed capacity statistics doubled; dispatch and costs unaffected.

**Fix** (see `pypsa-eur-code-modifications.instructions.md` §4): a `continue` guard in `add_power_capacities_installed_before_baseyear()` skips nuclear Links unconditionally (no config switch needed). Nuclear plants are therefore represented exclusively as PPM Generators.

### 5.4 `conventional_generation` Links in Sector Network

Default: `sector.conventional_generation: {OCGT: gas, CCGT: gas}`.

`add_generation()` (line 1317 of `prepare_sector_network.py`) adds a **Link** for each entry with:
- `p_nom = 0` (because `keep_existing_capacities: false` → `existing_capacities = None`)
- `p_nom_min = 0`
- `p_nom_extendable = False` (OCGT/CCGT are not in `extendable_carriers.Generator: []`)

With all three at zero, these Links are **inert** — they cannot dispatch anything. They do **not** interfere with the PPM-sourced OCGT/CCGT **Generators** from the electricity pipeline; the two components coexist under different PyPSA component classes (Link vs Generator) and different names.

`add_carrier_buses()` is also called for the `gas` carrier, creating per-node gas buses even with `gas_network: false`. This is a side effect required for Link `bus0` connectivity; it does not activate a dispatchable gas reticulation network.

Optional improvement: set `conventional_generation: {}` in the override config to suppress the zero-capacity Links entirely and keep the sector network leaner.

### 5.5 `regional_{fuel}_demand` Flags

These flags control the spatial resolution of **demand** buses. Critically, the **supply** buses are **always EU-wide** regardless of the flag value — this is hardcoded in `define_spatial()`:

```python
# scripts/prepare_sector_network.py, define_spatial() — always set, never conditioned on the flag:
spatial.oil.nodes     = ["EU oil"]       # supply bus — always EU
spatial.oil.locations = ["EU"]           # always EU
spatial.coal.nodes    = ["EU coal"]      # supply bus — always EU
spatial.methanol.nodes = ["EU methanol"] # supply bus — always EU
```

The flag only controls the `demand_locations` and named demand bus lists (`naphtha`, `kerosene`, `shipping`, etc.):

| Flag | Default | When `true` | When `false` |
|---|---|---|---|
| `regional_oil_demand` | `true` | per-node demand buses (e.g., `"DE0 naphtha for industry"`) | single demand bus (e.g., `"EU naphtha for industry"`) |
| `regional_coal_demand` | `false` | per-node demand buses (e.g., `"DE0 coal for industry"`) | `"EU coal for industry"` |
| `methanol.regional_methanol_demand` | `false` | per-node demand buses | `"EU shipping methanol"` etc. |

In all cases, `spatial.oil.nodes = ["EU oil"]` remains the **single supply bus** — it is the `bus0` for PPM-sourced oil generators in `add_existing_baseyear.py`. Changing `regional_oil_demand` does **not** alter the supply side.

With all demand sectors disabled, neither the demand buses nor the supply-to-demand Links are ever created, making these flags **fully irrelevant** in the electricity-only setup. `regional_oil_demand: false` is set explicitly as defensive documentation: it makes the intended EU-wide supply topology explicit and prevents confusion if demand sectors are ever re-enabled.

### 5.6 H2 Electrolysis and H2 Store Suppression via `adjustments`

`add_h2_gas_infrastructure()` in `prepare_sector_network.py` adds H2 buses and H2 Electrolysis Links **unconditionally** (lines 1841–1856), regardless of `H2_network`, `hydrogen_fuel_cell`, or `hydrogen_underground_storage` flags:

```python
n.add("Bus", nodes + " H2", ...)                    # always added
n.add("Link", nodes + " H2 Electrolysis",
      p_nom_extendable=True, ...)                    # always added — no flag guard
```

H2 Fuel Cell and H2 Turbine have explicit `if options[...]:` guards; H2 underground storage is guarded by `if options["hydrogen_underground_storage"]:`. But H2 Electrolysis is always created with `p_nom_extendable=True`, making it an unintended investment variable in the electricity-only model.

The `adjustments` block suppresses this:

```yaml
adjustments:
  sector:
    absolute:
      Link:
        H2 Electrolysis:
          p_nom_max: 0.0   # caps extendable capacity at zero → no investment, no dispatch
      Store:
        H2 Store:
          e_nom_max: 0.0   # caps any H2 Store that may be added
```

### 5.7 Backcasting Recommendations for Sector Scope

The following settings are **constant across all backcasting years** and must be set once in the base config (`config.rmi.yaml`):

```yaml
pypsa_eur:
  Generator:
  - onwind
  - "offwind-ac"
  - "offwind-dc"
  - "offwind-float"
  - "solar-hsat"
  - solar
  - ror
  - nuclear
  - biomass  # keeps PPM biomass Generators; remove_elec_base_techs() checks this list

sector:
  # Demand sectors — all disabled
  transport: false
  heating: false
  industry: false
  shipping: false
  aviation: false
  agriculture: false

  # Biomass — override default (true) to prevent infeasibility from mandatory-dispatch supply bus
  biomass: false    # no "EU solid biomass" bus; PPM biomass plants preserved as simple AC Generators
                    # via pypsa_eur.Generator list above.
                    # biomass_boiler / biogas_upgrading / biomass_to_liquid / electrobiofuels:
                    # NOT needed (all 4 inside add_biomass(), never called when biomass: false)

  # H2 and energy conversion — disable
  dac: false
  co2_network: false
  co2_spatial: false
  regional_co2_sequestration_potential:
    enable: false
  H2_network: false
  hydrogen_fuel_cell: false
  hydrogen_turbine: false
  SMR: false
  SMR_cc: false
  gas_network: false
  gas_distribution_grid: false
  electricity_distribution_grid: false   # no distribution grid in electricity-only (default: true)
  ammonia: false
  methanation: false
  hydrogen_underground_storage: false

  # Methanol sub-flags — override defaults that add investment variables
  methanol:
    biomass_to_methanol: false   # default: true → adds investment variables
    methanol_to_power:
      ocgt: false                # default: true → adds investment variables

  regional_oil_demand: false     # EU-wide oil bus (consistent with electricity-network PPM generators)

adjustments:
  sector:
    absolute:
      Link:
        H2 Electrolysis:
          p_nom_max: 0.0   # H2 Electrolysis always added unconditionally with p_nom_extendable=True
      Store:
        H2 Store:
          e_nom_max: 0.0   # suppress any H2 Store that slips through flag guards
```

---

## 6. Technology Costs: Availability and Backcasting Strategy

### 6.1 Problem: Cost File Availability for Intermediate Years

The upstream PyPSA-Eur cost database (technology-data v0.14.0) provides cost files only for a fixed set of milestone years: 2020, 2025, 2030, 2035, 2040, 2045, 2050. For intermediate years (e.g., 2021–2024), no cost files are available for direct download. However, the workflow and scripts expect a cost file named `costs_{Y}.csv` for every scenario year Y.

**Solution:**
- For any backcasting year Y without a dedicated cost file, the workflow automatically generates `costs_{Y}.csv` by copying the nearest available milestone file (typically `costs_2025.csv` for 2021–2024). This is handled by a dedicated Snakemake rule (`copy_cost_data_for_backcasting`).
- The copied file is then processed as usual to produce `costs_{Y}_processed.csv`.
- This approach ensures that all required cost files exist for any backcasting year, even if not present in the upstream archive.

### 6.2 Fuel Price Backcasting

While most cost parameters (capital costs, efficiency, lifetimes) can be safely inherited from the nearest milestone year, **fuel prices** (gas, coal, oil) vary significantly year by year and must be set correctly for each backcasting year to avoid distorting dispatch results.

**Strategy:**
- For each backcasting year Y, override the fuel price for each relevant technology in `data/custom_costs.csv`.
- The workflow uses static annual-average prices (`conventional.dynamic_fuel_price: false`), which are sufficient given the snapshot structure.
- All other cost parameters can remain as in the reference milestone file.

**Summary:**
- The combination of milestone file copying and per-year fuel price overrides ensures that the model uses historically accurate cost and fuel price data for every backcasting year, even when the upstream archive is incomplete.

---

## 7. Backcasting Implementation Strategy

### 7.1 Core Principle

For backcasting to year Y, **`scenario.planning_horizons: [Y]`** must match the target year. This single parameter change propagates to:
- `baseyear = Y` in `add_existing_baseyear.py`
- IRENASTAT data clipped at year Y
- Cost file: `costs_Y_processed.csv` (must exist)

All other changes listed below follow from this primary constraint.

### 7.2 Required Configuration Changes per Year Y

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

energy:
  energy_totals_year: <min(Y, 2023)>   # ← 6. statistical energy data reference year
  # Two constraints apply simultaneously:
  #
  # (a) ValueError constraint: build_central_heating_temperature_profiles raises
  #     ValueError if planning_horizons[0] < energy_totals_year → requires energy_totals_year ≤ Y.
  #
  # (b) Data availability constraint: only jrc_idees/archive/2023-v1 is downloaded for
  #     the GHGP project → max usable year is 2023. JRC IDEES does not publish data
  #     for years beyond ~2 years before release; no 2024/2025 data exists.
  #
  # Combined rule: energy_totals_year = min(Y, 2023)
  #   Y ∈ {2020, 2021, 2022}: use Y (constraint (a) forces it; 2023 default would crash)
  #   Y ∈ {2023, 2024, 2025}: use 2023 (latest available; constraint (a) satisfied since Y ≥ 2023)
  #
  # In a fully general model, the ideal value would be Y (best match to backcasting year).
  # The 2023 cap is a GHGP-project-specific limitation from the downloaded dataset.

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

pypsa_eur:
  Generator:
  - onwind
  - "offwind-ac"
  - "offwind-dc"
  - "offwind-float"
  - "solar-hsat"
  - solar
  - ror
  - nuclear
  - biomass  # ← 6c. keeps PPM biomass Generators; remove_elec_base_techs() checks this list

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
  # Demand sectors — all disabled
  transport: false             # ← 11. no transport demand
  heating: false               #    no heat demand
  industry: false              #    no industry demand
  shipping: false              #    no shipping demand
  aviation: false              #    no aviation demand
  agriculture: false           #    no agriculture demand
  electricity_distribution_grid: false  # ← 12. no distribution grid (default: true)

  # Biomass — override default to prevent infeasibility; sub-flags not needed (inside add_biomass())
  biomass: false               # ← 13. prevents "EU solid biomass" bus + mandatory-dispatch Generator
                               #    PPM biomass plants preserved via pypsa_eur.Generator (item 6c)
                               #    NOTE: biomass_boiler / biogas_upgrading / biomass_to_liquid /
                               #    electrobiofuels NOT needed — all 4 inside add_biomass()
  methanol:
    biomass_to_methanol: false # ← 14. adds investment variables (default: true)
    methanol_to_power:
      ocgt: false              # ← 15. adds investment variable (default: true)

  # Other sector components — disable to avoid crashes or investment variables
  dac: false
  co2_network: false
  co2_spatial: false
  regional_co2_sequestration_potential:
    enable: false
  H2_network: false
  hydrogen_fuel_cell: false
  hydrogen_turbine: false
  SMR: false
  SMR_cc: false
  gas_network: false
  gas_distribution_grid: false
  ammonia: false
  methanation: false
  hydrogen_underground_storage: false
  regional_oil_demand: false   # ← defensive/documentary only: supply bus is always "EU oil" regardless
                               #   (flag only affects demand buses, which are never created when all
                               #    demand sectors are disabled)

adjustments:
  sector:
    absolute:
      Link:
        H2 Electrolysis:
          p_nom_max: 0.0   # ← 16. H2 Electrolysis always added unconditionally with p_nom_extendable=True
      Store:
        H2 Store:
          e_nom_max: 0.0   # ← 17. suppress any H2 Store that slips through flag guards

solving:
  options:
    load_shedding: true  # ← 18. allow load shedding at high marginal cost to ensure feasibility in
                         #    dispatch-only mode. Default: false. Required because the model has no
                         #    capacity expansion and the historical system may be infeasible for some
                         #    snapshots (e.g., due to network constraints or missing flexibility).
```

### 7.3 Fuel Price Data Table (data/custom_costs.csv)

The following rows are used in `data/custom_costs.csv` to set annual-average fuel prices for each backcasting year:

| planning_horizon | technology | parameter | value | unit | source | further description |
|---|---|---|---|---|---|---|
| 2020 | gas | fuel | 10.00 | EUR/MWh_th | World Bank CMO Pink Sheet (Natural gas Europe) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2021 | gas | fuel | 41.40 | EUR/MWh_th | World Bank CMO Pink Sheet (Natural gas Europe) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2022 | gas | fuel | 117.03 | EUR/MWh_th | World Bank CMO Pink Sheet (Natural gas Europe) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2023 | gas | fuel | 40.40 | EUR/MWh_th | World Bank CMO Pink Sheet (Natural gas Europe) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2024 | gas | fuel | 29.22 | EUR/MWh_th | World Bank CMO Pink Sheet (Natural gas Europe) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2025 | gas | fuel | 29.87 | EUR/MWh_th | World Bank CMO Pink Sheet (Natural gas Europe) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2020 | coal | fuel | 8.24 | EUR/MWh_th | World Bank CMO Pink Sheet (Coal South African) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2021 | coal | fuel | 13.98 | EUR/MWh_th | World Bank CMO Pink Sheet (Coal South African) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2022 | coal | fuel | 29.20 | EUR/MWh_th | World Bank CMO Pink Sheet (Coal South African) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2023 | coal | fuel | 14.22 | EUR/MWh_th | World Bank CMO Pink Sheet (Coal South African) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2024 | coal | fuel | 11.69 | EUR/MWh_th | World Bank CMO Pink Sheet (Coal South African) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2025 | coal | fuel | 9.93 | EUR/MWh_th | World Bank CMO Pink Sheet (Coal South African) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2020 | oil | fuel | 22.51 | EUR/MWh | World Bank CMO Pink Sheet (Crude oil Brent) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2021 | oil | fuel | 33.67 | EUR/MWh | World Bank CMO Pink Sheet (Crude oil Brent) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2022 | oil | fuel | 50.18 | EUR/MWh | World Bank CMO Pink Sheet (Crude oil Brent) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2023 | oil | fuel | 38.96 | EUR/MWh | World Bank CMO Pink Sheet (Crude oil Brent) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2024 | oil | fuel | 36.71 | EUR/MWh | World Bank CMO Pink Sheet (Crude oil Brent) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
| 2025 | oil | fuel | 29.57 | EUR/MWh | World Bank CMO Pink Sheet (Crude oil Brent) via build_fossil_fuel_prices workflow (EUR2020 real) | Annual average of monthly values deflated to EUR2020 using IMF GDP deflator; derived from resources/monthly_fuel_price.csv |
```

### 7.4 Rules Requiring Changes

No Snakemake rules require code modification. The `add_existing_baseyear` rule's wildcard constraint:

```python
# rules/solve_myopic.smk
wildcard_constraints:
    planning_horizons=config["scenario"]["planning_horizons"][0]
```

automatically restricts the rule to run only for the first (and only) planning horizon. With `planning_horizons: [Y]`, it runs exclusively for year Y — correct behavior.

### 7.5 CO₂ Budget: Made Non-Binding for All Backcasting Years

`prepare_sector_network.py` calls `add_co2limit()` **unconditionally** — there is no enable/disable flag. The CO₂ budget value is resolved via `_helpers.get(co2_budget, investment_year)`, which looks up `investment_year` in the `co2_budget` dict from config and adds a `GlobalConstraint "CO2Limit"` to the network unless the resolved value is `None`.

`config.default.yaml` defines:

```yaml
co2_budget:
  2020: 0.72
  2025: 0.648
  2030: 0.45
  ...
```

These limits must be **non-binding** for all backcasting years in the GHGP project (see [039-rmi-ghgp.instructions.md](039-rmi-ghgp.instructions.md)). The project objective is to quantify the emission impact of an additional renewable energy project by comparing a baseline and a project scenario. If a binding CO₂ cap were active, the optimizer would respect it in both scenarios identically: once the cap is met, there is no further incentive to reduce emissions, and the marginal emission impact of the additional renewable would be absorbed elsewhere rather than reflected in a genuine emission difference. To preserve the causal signal between the project and system-level emissions, no binding CO₂ constraint must be imposed.

Set the following in `config/test/config.rmi.yaml` (once, applies to all backcasting years):

```yaml
co2_budget:
  2020: 1.0
  2025: 1.0
```

`1.0` means "emissions ≤ 100% of 1990 levels". Actual European electricity-sector emissions in 2020–2025 are well below 1990 levels, so the constraint is never binding. This approach requires no changes to the PyPSA-Eur validation schema.

Only the two milestone years are needed. `_helpers.get()` interpolates linearly between keys when the investment year is not found; since all values are `1.0`, the interpolated result for 2021–2024 is also `1.0`. Note that `_helpers.get()` emits a `logger.warning` for each missing key — this is harmless but produces log noise. Adding the intermediate years explicitly suppresses those warnings.

**Note on dict merging**: Snakemake merges `config.rmi.yaml` over `config.default.yaml` with a deep-merge strategy. The merged `co2_budget` dict will still contain keys for years beyond 2025 (e.g., `2030: 0.45`). This is acceptable: no backcasting scenario uses a `planning_horizons` value beyond 2025, so those keys are never resolved.

---

## 8. Cross-Reference: Config → Code Mapping

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
| `sector.biomass` | `prepare_sector_network` | `prepare_sector_network.py` | 3764 | `false` (override) → `add_biomass()` not called; no `"EU solid biomass"` bus; no mandatory-dispatch Generator; PPM biomass Generators preserved via `pypsa_eur.Generator` |
| `pypsa_eur.Generator` | `prepare_sector_network` | `prepare_sector_network.py` | 656 | includes `biomass` → `remove_elec_base_techs()` keeps PPM biomass Generators; default list omits `biomass` → they would be dropped otherwise |
| `sector.methanol.biomass_to_methanol` | `prepare_sector_network` | `prepare_sector_network.py` | — | `true` (default) adds methanol investment variables → must be `false` |
| `sector.methanol.methanol_to_power.ocgt` | `prepare_sector_network` | `prepare_sector_network.py` | — | `true` (default) adds OCGT methanol Link with `p_nom_extendable=True` → must be `false` |
| `sector.conventional_generation` | `prepare_sector_network` | `prepare_sector_network.py` | 1317 | Default `{OCGT: gas, CCGT: gas}` → `add_generation()` adds zero-capacity (`p_nom=0`, not extendable) Links; harmless but adds inert components; optional: override with `{}` |
| `sector.regional_oil_demand` | `prepare_sector_network` | `prepare_sector_network.py` | 160 | `false` → single `"EU oil"` bus; `true` → per-node oil buses; irrelevant when all demand sectors disabled, but `false` is consistent with electricity-only PPM generator bus assignment |
| `adjustments.sector.absolute.Link.H2 Electrolysis.p_nom_max` | `prepare_sector_network` | `prepare_sector_network.py` | 1843 | `0.0` → caps the unconditionally-added `p_nom_extendable=True` H2 Electrolysis Link at zero capacity; prevents investment and dispatch |
| `adjustments.sector.absolute.Store.H2 Store.e_nom_max` | `prepare_sector_network` | `prepare_sector_network.py` | 1916 | `0.0` → caps any H2 Store created (underground or overground) at zero energy capacity |
| `costs.year` | `add_electricity`, `prepare_network` | multiple | — | Cost file year for overnight mode / pre-baseyear rules |
| `conventional.dynamic_fuel_price` | `add_electricity` | `add_electricity.py` | ~1370 | `false` → static marginal_cost from processed CSV; `true` → hourly marginal_cost from `monthly_fuel_price.csv` |
| `custom_costs.csv` `fuel` param | `process_cost_data` | `process_cost_data.py` | 178-183 | Raw attr override: sets `gas.fuel` → auto-propagates to OCGT/CCGT → recomputes `marginal_cost = VOM + fuel/efficiency` |
| `custom_costs.csv` `marginal_cost` param | `process_cost_data` | `process_cost_data.py` | Stage 2 | Prepared attr override: directly sets final `marginal_cost`, bypasses computation |
| `energy.energy_totals_year` | `build_central_heating_temperature_profiles`, `build_energy_totals`, `build_transport_demand`, `build_district_heat_share` | multiple | — | Reference year for JRC IDEES / Eurostat statistical data. Two constraints: (a) must be ≤ `planning_horizons[0]` (ValueError otherwise); (b) must be ≤ max available in downloaded dataset (2023 for GHGP). Combined rule: `min(Y, 2023)`. For Y < 2023: set to Y (constraint a forces it). For Y ≥ 2023: set to 2023 (data availability cap). |
| `biomass.share_unsustainable_use_retained` | `build_biomass_potentials` | `build_biomass_potentials.py` | 299 | `.get(investment_year)` — returns None for non-milestone years → must add explicit key Y in config |
| `biomass.share_sustainable_potential_available` | `build_biomass_potentials` | `build_biomass_potentials.py` | 327 | `.get(investment_year)` — same unsafe lookup — must add explicit key Y in config |
