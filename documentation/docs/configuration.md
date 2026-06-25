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

---

## Test model configurations