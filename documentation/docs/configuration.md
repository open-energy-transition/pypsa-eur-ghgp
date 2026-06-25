# Configuration

This section includes all the configuration settings characterizing the available scenarios. These settings have been defined aiming to develop a dispatch-only model for the historical period 2020-2025. Also, the differences compared to the default configuration settings are described.

The full model configurations are defined in two files:
- [`config/config.rmi.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/config.rmi.yaml), which includes the common settings across the available scenarios.
- [`config/scenarios.rmi.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/scenarios.rmi.yaml), which includes the scenario specific settings.

Consider that PyPSA-Eur utilizes a hierarchical configuration structure to manage its modeling assumptions and scenarios. In particular, the default settings defined in [`config/config.default.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/config.default.yaml) are overwritten by the ones in `config/config.rmi.yaml`, which in turn are overwritten by the ones in `config/scenarios.rmi.yaml`. For more details on the default configuration settings, see the [original PyPSA-Eur documentation](https://pypsa-eur.readthedocs.io/en/latest/configuration/).

---

## Common settings (`config/config.rmi.yaml`)

All the common settings and properties are described below, pointing out only the differences with the default ones.

### `run`

Section to define scenarios to run.

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `name` | list | `["baseline-2024-3H"]` | `""` | Scenario name(s); overridden per-scenario in `scenarios.rmi.yaml` |
| `scenarios` | — | — | — | Multi-scenario run management |
| &nbsp;&nbsp;`↳ enable` | bool | `true` | `false` | Activate multi-scenario mode |
| &nbsp;&nbsp;`↳ file` | str | `"config/scenarios.rmi.yaml"` | `"config/scenarios.yaml"` | Path to the scenarios file |

```yaml
run:
  prefix: ""
  name:
  - baseline-2024-3H
  scenarios:
    enable: true
    file: config/scenarios.rmi.yaml
  disable_progressbar: false
  shared_resources:
    policy: false
    exclude: []
  use_shadow_directory: false
```

### `foresight`

Section to define the foresight mode.

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `foresight` | str | `myopic` | `overnight` | Optimization foresight mode |

```yaml
foresight: myopic
```

### `scenario`

Section strongly connected to the wildcards (for more details, see the [original PyPSA-Eur documentation](https://pypsa-eur.readthedocs.io/en/latest/configuration/#wildcards)), which is designed to facilitate running multiple scenarios through a single command

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `clusters` | list[int] | `[39]` | `[50]` | Number of nodes the network is clustered to |
| `planning_horizons` | list[int] | `[2024]` | `[2050]` | Simulation year(s); overridden per-scenario in `scenarios.rmi.yaml` |

```yaml
scenario:
  clusters:
  - 39
  opts:
  - ""
  sector_opts:
  - ""
  planning_horizons:
  - 2024
```

### `co2_budget`

Section to control CO2 emission constraint.

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `2020` | float | `1.0` | `0.72` | CO₂ budget for 2020 (fraction of 1990 emission levels) |
| `2025` | float | `1.0` | `0.648` | CO₂ budget for 2025 (fraction of 1990 emission levels) |

Set to `1.0` (100 % of 1990 levels) to make the constraint non-binding: actual European emissions in 2020–2025 are well below 1990 levels, so the cap never activates. This avoids distorting the emission impact signal between baseline and project scenarios.

```yaml
co2_budget:
  2020: 1.0
  2025: 1.0
```

### `backcasting`

Project-specific block with no equivalent in the default config. It controls cost data alignment to non-default years and project generator injection.

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `enable` | bool | `true` | n/a | Activate the backcasting cost-copy Snakemake workflow |
| `year_costs` | int | `2025` | n/a | Milestone year whose cost file is copied to non-milestone years (e.g. `costs_2025.csv` → `costs_2024.csv`) |
| `project` | — | — | — | Project generator settings |
| &nbsp;&nbsp;`↳ enable` | bool | `false` | n/a | Inject a project generator; overridden to `true` in project scenarios |
| &nbsp;&nbsp;`↳ file` | str | `"data/project_generators.csv"` | n/a | CSV with project generator definitions |
| &nbsp;&nbsp;`↳ carrier` | list[str] | `["solar"]` | n/a | Technology carrier of the project generator |
| &nbsp;&nbsp;`↳ size_MW` | list[float] | `[100]` | n/a | Installed capacity of the project generator (MW) |
| &nbsp;&nbsp;`↳ country` | list[str] | `["DE"]` | n/a | Country/bus code where the project generator is located |

```yaml
backcasting:
  enable: true
  year_costs: 2025
  project:
    enable: false
    file: data/project_generators.csv
    carrier: ["solar"]
    size_MW: [100]
    country: ["DE"]
```

### `electricity`

Section for electricity-specific configuration.

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `extendable_carriers` | — | — | — | Carriers whose installed capacity can be expanded by the optimizer |
| &nbsp;&nbsp;`↳ Generator` | list | `[]` | `[solar, solar-hsat, onwind, offwind-ac, offwind-dc, offwind-float, OCGT, CCGT]` | Extendable generator carriers |
| &nbsp;&nbsp;`↳ StorageUnit` | list | `[]` | `[]` | Extendable storage unit carriers |
| &nbsp;&nbsp;`↳ Store` | list | `[]` | `[battery, H2]` | Extendable store carriers |
| &nbsp;&nbsp;`↳ Link` | list | `[]` | `[]` | Extendable link carriers |
| `transmission_limit` | str | `v1.0` | `vopt` | Transmission expansion limit. `v1.0` fixes lines at current capacities; `vopt` allows optimization |

All `extendable_carriers` are set to `[]` to enforce a pure dispatch optimization without any capacity expansion.

```yaml
electricity:
  extendable_carriers:
    Generator: []
    StorageUnit: []
    Store: []
    Link: []
  transmission_limit: v1.0
```

### `lines`

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `under_construction` | str | `zero` | `keep` | Treatment of OSM lines flagged as under construction. `zero`: present in topology but `s_nom = 0`; `keep`: full rated capacity; `remove`: removed entirely |

```yaml
lines:
  under_construction: zero
```

### `transmission_projects`

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `enable` | bool | `false` | `true` | Include planned transmission projects (TYNDP, etc.) in the network |

```yaml
transmission_projects:
  enable: false
```

### `pypsa_eur`

Defines which component types are retained from the PyPSA-Eur base network before sector coupling.

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `Generator` | list[str] | `[onwind, offwind-ac, offwind-dc, offwind-float, solar-hsat, solar, ror, nuclear, **biomass**]` | same without `biomass` | Generator carrier types to retain. `biomass` is added to preserve historical biomass power plants as simple AC-connected generators |

```yaml
pypsa_eur:
  Bus:
  - AC
  Link:
  - DC
  Generator:
  - onwind
  - "offwind-ac"
  - "offwind-dc"
  - "offwind-float"
  - "solar-hsat"
  - solar
  - ror
  - nuclear
  - biomass
  StorageUnit:
  - PHS
  - hydro
  Store: []
```

### `sector`

Section to control whether to include or not sectors other than the electricity one.

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `biomass` | bool | `false` | `true` | Biomass sector |
| `transport` | bool | `false` | `true` | Transport sector |
| `heating` | bool | `false` | `true` | Heating sector |
| `industry` | bool | `false` | `true` | Industry sector |
| `shipping` | bool | `false` | `true` | Shipping sector |
| `aviation` | bool | `false` | `true` | Aviation sector |
| `agriculture` | bool | `false` | `true` | Agriculture sector |
| `dac` | bool | `false` | `true` | Direct air capture |
| `co2_network` | bool | `false` | `true` | CO₂ transport network |
| `co2_spatial` | bool | `false` | `true` | Spatially resolved CO₂ tracking |
| `regional_co2_sequestration_potential` | — | — | — | |
| &nbsp;&nbsp;`↳ enable` | bool | `false` | `true` | Regional CO₂ sequestration potential |
| `H2_network` | bool | `false` | `true` | Hydrogen transport network |
| `hydrogen_fuel_cell` | bool | `false` | `true` | Hydrogen fuel cells |
| `hydrogen_turbine` | bool | `false` | `true` | Hydrogen turbines |
| `SMR` | bool | `false` | `true` | Steam methane reforming (SMR)|
| `SMR_cc` | bool | `false` | `true` | SMR with carbon capture |
| `gas_network` | bool | `false` | `true` | Gas transmission network |
| `gas_distribution_grid` | bool | `false` | `true` | Gas distribution grid |
| `electricity_distribution_grid` | bool | `false` | `true` | Electricity distribution grid |
| `ammonia` | bool | `false` | `true` | Ammonia sector |
| `methanol` | — | — | — | |
| &nbsp;&nbsp;`↳ biomass_to_methanol` | bool | `false` | `true` | Biomass-to-methanol conversion |
| &nbsp;&nbsp;`↳ methanol_to_power.ocgt` | bool | `false` | `true` | Methanol-fuelled OCGT |
| `hydrogen_underground_storage` | bool | `false` | `true` | Underground hydrogen storage |
| `methanation` | bool | `false` | `true` | Power-to-gas methanation |
| `regional_oil_demand` | bool | `false` | `true` | Regional oil demand buses |

```yaml
sector:
  biomass: false
  transport: false
  heating: false
  industry: false
  shipping: false
  aviation: false
  agriculture: false
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
  electricity_distribution_grid: false
  ammonia: false
  methanol:
    biomass_to_methanol: false
    methanol_to_power:
      ocgt: false
  hydrogen_underground_storage: false
  methanation: false
  regional_oil_demand: false
```

All sector-coupled demand and supply sectors are disabled to run a pure electricity dispatch model.

### `costs`

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `emission_prices` | — | — | — | CO₂ price settings applied to marginal costs |
| &nbsp;&nbsp;`↳ enable` | bool | `true` | `false` | Apply a CO₂ price to marginal costs |
| &nbsp;&nbsp;`↳ co2` | float | `50` | n/a | CO₂ price in €/tCO₂ (≈ yearly average ETS price 2020–2025) |

```yaml
costs:
  emission_prices:
    enable: true
    co2: 50
```

### `clustering`

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `temporal` | — | — | — | Temporal resolution settings |
| &nbsp;&nbsp;`↳ resolution_sector` | str | `3H` | `false` | Temporal aggregation of the sector network. `3H` → 3-hour intervals; `false` → full hourly resolution |

```yaml
clustering:
  temporal:
    resolution_sector: 3H
```

### `adjustments`

Post-build capacity overrides applied after the network is assembled. Used to enforce zero capacity on H2 infrastructure unconditionally added by `prepare_sector_network.py`.

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `sector` | — | — | — | |
| &nbsp;&nbsp;`↳ absolute` | — | — | `false` | Absolute capacity overrides per component |
| &nbsp;&nbsp;&nbsp;&nbsp;`↳ Link` | — | — | — | |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`↳ H2 Electrolysis.p_nom_max` | float | `0.0` | `false` | Forces H2 Electrolysis installed capacity to zero |
| &nbsp;&nbsp;&nbsp;&nbsp;`↳ Store` | — | — | — | |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`↳ H2 Store.e_nom_max` | float | `0.0` | `false` | Forces H2 Store energy capacity to zero |

```yaml
adjustments:
  sector:
    absolute:
      Link:
        H2 Electrolysis:
          p_nom_max: 0.0
      Store:
        H2 Store:
          e_nom_max: 0.0
```

### `solving`

| Property | Type | Value | Default | Description |
|---|---|---|---|---|
| `options` | — | — | — | Solver options |
| &nbsp;&nbsp;`↳ load_shedding` | bool | `true` | `false` | Add a load-shedding generator at every bus to prevent numerical infeasibility |

```yaml
solving:
  options:
    load_shedding: true
```

---

## Scenario specific settings (`config/scenarios.rmi.yaml`)

All the Scenario specific settings and properties are described below, pointing out only the differences with the default ones. Each scenario is identified by a unique name (e.g., `baseline-2024-3H`), and the settings below describe how each property varies across the available scenarios.

### Baseline scenarios

Six baseline scenarios are available, one per backcasting year: `baseline-2020-3H`, `baseline-2021-3H`, `baseline-2022-3H`, `baseline-2023-3H`, `baseline-2024-3H`, `baseline-2025-3H`. Each represents a full-year dispatch simulation of the European electricity system for the corresponding historical year.

#### `scenario`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `planning_horizons` | list[int] | `[2020]` | `[2021]` | `[2022]` | `[2023]` | `[2024]` | `[2025]` | `[2050]` | Simulation year; controls the IRENASTAT cutoff, existing capacity baseyear, and cost file selection |

```yaml
# Example: baseline-2024-3H
scenario:
  planning_horizons:
  - 2024
```

#### `atlite`

This section controls the calculation of renewable potentials and time-series (i.e., the weather year).

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `default_cutout` | str | `europe-2020-sarah3-era5` | `europe-2021-sarah3-era5` | `europe-2022-sarah3-era5` | `europe-2023-sarah3-era5` | `europe-2024-sarah3-era5` | `europe-2025-sarah3-era5` | `europe-2013-sarah3-era5` | ERA5 weather cutout used for renewable capacity factor profiles |

The weather year is chosen equal to the simulation year.

```yaml
# Example: baseline-2024-3H
atlite:
  default_cutout: "europe-2024-sarah3-era5"
```

#### `snapshots`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `start` | str | `2020-01-01` | `2021-01-01` | `2022-01-01` | `2023-01-01` | `2024-01-01` | `2025-01-01` | `2013-01-01` | Start date of the simulation |
| `end` | str | `2021-01-01` | `2022-01-01` | `2023-01-01` | `2024-01-01` | `2025-01-01` | `2026-01-01` | `2014-01-01` | End date of the simulation (exclusive) |

```yaml
# Example: baseline-2024-3H
snapshots:
  start: "2024-01-01"
  end: "2025-01-01"
  inclusive: left
```

#### `electricity`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `powerplants_filter` | str | `(DateOut > 2020 or DateOut != DateOut) and (DateIn < 2021 or DateIn != DateIn)` | same pattern with Y=2021 | Y=2022 | Y=2023 | Y=2024 | Y=2025 | `(DateOut > 2025 ...) and (DateIn < 2026 ...)` | pandas `.query()` string filtering PPM plants to those operating in year Y |

```yaml
# Example: baseline-2024-3H
electricity:
  powerplants_filter: "(DateOut > 2024 or DateOut != DateOut) and (DateIn < 2025 or DateIn != DateIn)"
```

#### `load`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `fixed_year` | int | `2020` | `2021` | `2022` | `2023` | `2024` | `2025` | `false` | Year whose historical demand profile is applied to the simulation snapshots. If `false`, the weather year is applied |

```yaml
# Example: baseline-2024-3H
load:
  fixed_year: 2024
```

#### `existing_capacities`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `grouping_years_power` | list[int] | no override | adds `2021` | adds `2022` | adds `2023` | adds `2024` | no override | `[..., 2020, 2025, 2030]` | Bin boundaries for assigning existing plants to vintage groups. The backcasting year Y is inserted between 2020 and 2025 to avoid zero-lifetime errors for plants built in (2020, Y] |

!!! note
    For 2020 and 2025, no override is needed because those years are already bin boundaries in the default list. For intermediate years (2021–2024), the year Y is added to the list to avoid a division-by-zero in the annuity calculation for recently-commissioned plants.

```yaml
# Example: baseline-2024-3H (adds 2024 between 2020 and 2025)
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
  - 2024
  - 2025
  - 2030
```

#### `costs`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `year` | int | `2020` | `2021` | `2022` | `2023` | `2024` | `2025` | `2050` | Technology cost year; selects the correct `costs_{year}.csv` file |

```yaml
# Example: baseline-2024-3H
costs:
  year: 2024
```

#### `biomass`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `share_unsustainable_use_retained` | — | no override | `{2021: 1.0}` | `{2022: 1.0}` | `{2023: 1.0}` | `{2024: 1.0}` | no override | `{2020: 1, 2050: 0}` | Fraction of unsustainable biomass use retained. The backcasting year Y must be added as a key so that `build_biomass_potentials` can look it up without interpolation |
| `share_sustainable_potential_available` | — | no override | `{2021: 0}` | `{2022: 0}` | `{2023: 0}` | `{2024: 0}` | no override | `{2020: 0, 2050: 1}` | Fraction of sustainable biomass potential available. Same reason as above |

!!! note
    These overrides are required even though `sector.biomass: false`, because `build_biomass_potentials` is an unconditional dependency of `prepare_sector_network` and uses `dict.get(year)` with no interpolation. Without the explicit entry, a `None` lookup would cause a runtime error.

```yaml
# Example: baseline-2024-3H
biomass:
  share_unsustainable_use_retained:
    2024: 1.0
  share_sustainable_potential_available:
    2024: 0
```

#### `energy`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `energy_totals_year` | int | `2020` | `2021` | `2022` | `2023` | `2023` | no override | `2023` | Year for JRC IDEES energy totals. Capped at 2023 because only `jrc_idees/archive/2023-v1` is available. For 2020, the actual year must be used because `2020 < 2023` would trigger a `ValueError` |

```yaml
# Example: baseline-2024-3H (capped at 2023)
energy:
  energy_totals_year: 2023
```

#### `backcasting`

| Property | Type | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Default | Description |
|---|---|---|---|---|---|---|---|---|---|
| `year_costs` | int | `2025` | `2025` | `2025` | `2025` | `2025` | no override | n/a | Milestone year whose cost file is copied to the backcasting year (e.g., `costs_2025.csv` → `costs_2024.csv`) |

```yaml
# Example: baseline-2024-3H
backcasting:
  year_costs: 2025
```

---

### Project scenarios

Project scenarios add a single renewable energy generator on top of the corresponding baseline network, representing a specific real-world investment (e.g., a solar PPA), and are used to compute the counterfactual emission impact.

Three project types have been modeled, one per geography:

| Project | Country | Carrier | Capacity | Description |
|---|---|---|---|---|
| `DE-solar-100MW` | Germany (`DE`) | `solar` | 100 MW | Representative utility-scale solar PPA in Germany, among the largest electricity market in the EU |
| `RO-solar-100MW` | Romania (`RO`) | `solar` | 100 MW | Solar PPA in Romania, a market with fast-growing renewable capacity |
| `GB30-onwind-100MW` | Great Britain — node `GB3 0` | `onwind` | 100 MW | Onshore wind project in the UK, representing a wind-dominated market |

Project generators are defined in [`data/project_generators.csv`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/data/project_generators.csv) and injected into the network by the `add_project_generators` Snakemake rule.

For each project type, six scenarios are available (one per year 2020–2025), named e.g. `project-2024-3H-DE-solar-100MW`. All year-specific settings (`scenario`, `atlite`, `snapshots`, `electricity`, `load`, `existing_capacities`, `costs`, `biomass`, `energy`) are **identical to the corresponding baseline scenario**, and are not repeated here for brevity.

The only additional setting compared to the baseline is `backcasting.project`, which is overridden to activate the project generator injection:

#### `backcasting.project`

| Property | Type | DE solar | RO solar | GB30 onwind | Default (common config) | Description |
|---|---|---|---|---|---|---|
| `enable` | bool | `true` | `true` | `true` | n/a | Activate project generator injection |
| `file` | str | `data/project_generators.csv` | same | same | n/a | CSV file with project generator definitions |
| `carrier` | list[str] | `["solar"]` | `["solar"]` | `["onwind"]` | n/a | Technology carrier of the project generator |
| `size_MW` | list[float] | `[100]` | `[100]` | `[100]` | n/a | Installed capacity in MW |
| `country` | list[str] | `["DE"]` | `["RO"]` | `["GB30"]` | n/a | Country/bus code where the generator is injected |

```yaml
# Example: project-2024-3H-DE-solar-100MW
# (year-specific settings identical to baseline-2024-3H, plus:)
backcasting:
  year_costs: 2025
  project:
    enable: true
    file: data/project_generators.csv
    carrier: ["solar"]
    size_MW: [100]
    country: ["DE"]
```

---

## Test model configurations

Finally, a test configuration has been developed for a test toy model, which was very useful in the initial phase of the model development. The files involved are:
- [`config/test/config.rmi.DE.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/test/config.rmi.DE.yaml).
- [`config/test/scenarios.rmi.DE.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/test/scenarios.rmi.DE.yaml).

The test model only includes Germany, modelled with 2 nodes. Also, the weather year is constant across all the scenarios and equal to default one, i.e., 2013.