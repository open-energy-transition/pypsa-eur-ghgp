# Scenarios

This section includes all the additional code compared to the [upstream PyPSA-EUR](https://github.com/open-energy-transition/pypsa-eur). These changes were needed to correctly develop and run the model.

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

---

## Modeling of additional renewable projects

---

## Interactive scenario run