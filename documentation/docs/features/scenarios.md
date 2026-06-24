# Scenarios

This section includes all the additional code compared to the [upstream PyPSA-EUR](https://github.com/open-energy-transition/pypsa-eur). These changes were needed to correctly develop and run the model.

---

## Modeling of additional renewable projects

---

## Scenario development

### Technology cost data alignment
**Affected files**
- **Script/function:** [`rules/retrieve.smk`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/rules/retrieve.smk)
- **Configuration settings:** `backcasting.enable` and `backcasting.year_costs`

**Motivation:**

The [upstream technology cost database](https://github.com/pypsa/technology-data) currently provides techno-economic parameters files only for milestone years from 2020 to 2050, with 5-years intervals. Instead, no files are created for intermediate years, e.g., 2021–2024. However, PyPSA-Eur expects a cost file named `costs_{planning_horizons[0]}.csv` for each scenario year. To enable backcasting for these years, a workflow is needed to generate the required cost files.

**Implementation:**

A new Snakemake rule, `copy_cost_data_for_backcasting`, is conditionally defined in `rules/retrieve.smk`:

```python
if config.get("backcasting", {}).get("enable", False):
    _year_costs = config["backcasting"]["year_costs"]

    rule copy_cost_data_for_backcasting:
        message:
            "Copying cost data from {_year_costs} to {wildcards.planning_horizons} for backcasting"
        input:
            costs=COSTS_DATASET["folder"] + f"/costs_{_year_costs}.csv",
        output:
            costs=COSTS_DATASET["folder"] + "/costs_{planning_horizons}.csv",
        wildcard_constraints:
            planning_horizons=f"(?!{_year_costs}$)\\d+",
        run:
            copy2(input["costs"], output["costs"])

    ruleorder: copy_cost_data_for_backcasting > retrieve_cost_data
```

- The rule is only active when `backcasting.enable: true`.
- It copies the user-defined upstream available milestone cost file in `backcasting.year_costs` (e.g., `costs_2025.csv`) to the required intermediate year (e.g., `costs_2024.csv`).
- The rule takes precedence over the default `retrieve_cost_data` rule for the same output file.
- Only the fossil fuel prices for each simulation year are exogenously set via [`data/custom_costs.csv`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/data/custom_costs.csv) overrides (source: [World Bank Commodity prices](https://www.worldbank.org/en/research/commodity-markets)).

### `noisy_costs` alignment
**Script/function:** [`scripts/solve_network.py/prepare_network()`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/scripts/solve_network.py#L423)

**Motivation:**

PyPSA-Eur applies by default small random perturbations to marginal costs (`solving.options.noisy_costs: true`) to mitigate potential optimization problem degeneracy and ensure a unique optimal solution. The pereturbation is implemented by means of `np.random.seed(solve_opts.get("seed", 123))`, before solving the network. In particular, the seed is fixed, so the sequence of perturbations is deterministic and depends on the number of components in the network.

However, the project scenarios add one (or more) generators to the baseline network. These project generators then shift by one (or more) positions the perturbation assignment of all the components after them. That means the components after the project generator(s) receive **different** noise perturbations in the two scenarios, creating inconsitency between the baseline and project scenarios (i.e., if the noise on the same components differs between baseline and project, the two problems are different).

**Implementation:**

Change the original code so that only all the components other than the project generators receive the same noise in both scenarios.

*Upstream code:*
```python
if solve_opts.get("noisy_costs"):
    for t in n.components:
        # if 'capital_cost' in t.static:
        #    t.static['capital_cost'] += 1e1 + 2.*(np.random.random(len(t.static)) - 0.5)
        if "marginal_cost" in t.static:
            t.static["marginal_cost"] += 1e-2 + 2e-3 * (
                np.random.random(len(t.static)) - 0.5
            )

    for t in n.components[["Line", "Link"]]:
        if t.static.empty:
            continue
        t.static["capital_cost"] += (
            1e-1 + 2e-2 * (np.random.random(len(t.static)) - 0.5)
        ) * t.static["length"]
```

*New code:*
```python
if solve_opts.get("noisy_costs"):
    for t in n.components:
        # if 'capital_cost' in t.static:
        #    t.static['capital_cost'] += 1e1 + 2.*(np.random.random(len(t.static)) - 0.5)
        if "marginal_cost" in t.static:
            mask = ~t.static.index.str.contains("project", case=False)
            idx = t.static.index[mask]
            t.static.loc[idx, "marginal_cost"] += 1e-2 + 2e-3 * (
                np.random.random(len(idx)) - 0.5
            )

    for t in n.components[["Line", "Link"]]:
        if t.static.empty:
            continue
        t.static["capital_cost"] += (
            1e-1 + 2e-2 * (np.random.random(len(t.static)) - 0.5)
        ) * t.static["length"]
```

Consider that the naming convention (`"project"` substring in generator names) is enforced by [`scripts/rmi/add_project_generators.py`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/scripts/rmi/add_project_generators.py): the injected generator name is `"{bus} {resource_class} {carrier}-project-{baseyear}"`. Also, the filter is only applied to generators, as renewable projects are added as `Generator` components. Any future projects added to [`data/project_generators.csv`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/data/project_generators.csv) must follow these conventions for the fix to remain effective.

---

## Interactive scenario run
**Script/function:** [`run/backcasting_run.py`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/run/backcasting_run.py).

**Motivation:**

This script has been developed for two main reasons:
1. Allow the user to interactively and automatically run the scenarios available in [`config/scenarios.rmi.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/scenarios.rmi.yaml) (for more details, see section [Introduction](introduction.md)).
2. Identify the resources (i.e., the intermediate files generated when running each scenario) that are common across the scenarios, reducing the number of rules included in the snakemake workflows. For more details on the pypsa workflow management, see the [Snakemake documentation](https://snakemake.readthedocs.io/en/stable/index.html).

**Implementation:**

Whereas the interactive steps are outlined in section [Introduction](introduction.md), the common resource management is here described. The common resources are shared across scenarios by using two symbolic link (symlink) strategies:

1. *Baseline → baseline (cross-year):* symlink only **year-indipendent files**.
   
    Many resource files (cutout profiles, geographic shapes, OSM network, busmap, etc.) do not depend on the simulation year and are identical across all baseline scenarios. The reference is always the `baseline-2025` scenario (detected automatically from the scenarios file).

    Year-independent files:
    - `availability_matrix_{clusters}_{tech}.nc`.
    - `regions_*.geojson` / `*_shapes.geojson`.
    - `networks/base*.nc`.
    - `busmap`, `linemap`, `pop_layout_{total,urban,rural}.nc`, `pop_layout_base_s_{c}.csv`.

2. *Baseline → project (same year):* symlink **all resource files**.
   
    A project scenario shares every configuration key with its same-year baseline: `planning_horizons`, `powerplants_filter`, `fixed_year`, `costs.year`, `energy_totals_year`, `biomass`, `existing_capacities`. Therefore, all resources up to and including `*_brownfield.nc` are identical. Only two rules need to run for a project scenario:
    - `add_project_generators`  (produces `*_brownfield_project.nc`).
    - `solve_sector_network_myopic`.