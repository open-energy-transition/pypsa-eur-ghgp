# PyPSA-Eur Code Modifications

This file documents all modifications made to the original PyPSA-Eur codebase in the context of the GHGP project. Each entry includes a description of the bug or motivation, the affected files and locations, and the exact change applied. This is intended to facilitate upstreaming of fixes to the PyPSA-Eur repository.

---

## 1. VOM unit conversion bug in Link `marginal_cost`

### Background

In PyPSA, the `marginal_cost` attribute of a `Link` must be expressed in **EUR/MWh_bus0** (i.e., per unit of energy at the fuel input port, `p0`). This is because the PyPSA objective function multiplies `marginal_cost × p0 × snapshot_weighting` (verified from `pypsa/optimization/optimize.py` and `pypsa/data/variables.csv`, where the marginal cost flag is set on the `p` variable of Links, which corresponds to `p0`).

The cost database provides `VOM` values in **EUR/MWh_el** (or EUR/MWh output more generally). Therefore, the correct conversion when setting `marginal_cost` for a Link is:

```
marginal_cost [EUR/MWh_fuel] = efficiency [MWh_el/MWh_fuel] × VOM [EUR/MWh_el]
```

### Bug

In multiple places across `prepare_sector_network.py` and `add_existing_baseyear.py`, `marginal_cost` was set directly to `costs.at[tech, "VOM"]` without multiplying by efficiency. This caused an overestimation of the effective marginal cost by a factor of `1/η`. For example, for `central solid biomass CHP` (η=0.2694, VOM=6.1352 EUR/MWh_el), the effective marginal cost per MWh_el was 22.8 EUR/MWh_el instead of the correct 6.14 EUR/MWh_el (factor ~3.7×).

### Fix

All instances of the pattern:
```python
marginal_cost=costs.at[tech, "VOM"],
```
were corrected to:
```python
marginal_cost=costs.at[tech, "efficiency"] * costs.at[tech, "VOM"],  # NB: VOM is per MWh_el
```
(with the appropriate efficiency key for each technology).

### Affected files and locations

#### `scripts/add_existing_baseyear.py`

| Location | Technology | Fix |
|---|---|---|
| `add_power_capacities_installed_before_baseyear()`, `else` branch for `urban central solid biomass CHP` | `central solid biomass CHP` | `costs.at[key, "efficiency"] * costs.at[key, "VOM"]` |

#### `scripts/prepare_sector_network.py`

| Function | Technology | Efficiency key used |
|---|---|---|
| `add_methanol_to_power()` | `CCGT methanol` | `costs.at["CCGT", "efficiency"]` |
| `add_methanol_to_power()` | `CCGT methanol CC` | `costs.at["CCGT", "efficiency"]` |
| `add_h2_gas_infrastructure()` | `H2 turbine` | `costs.at["OCGT", "efficiency"]` |
| `add_heat()` | `urban central {fuel} CHP` | `costs.at["central gas CHP", "efficiency"]` |
| `add_heat()` | `urban central {fuel} CHP CC` | `costs.at["central gas CHP", "efficiency"]` |
| `add_biomass()` | `central solid biomass CHP` (extendable) | `costs.at[key, "efficiency"]` |
| `add_biomass()` | `central solid biomass CHP CC` (extendable) | `costs.at[key + " CC", "efficiency"]` |
| `add_biomass()` | `biogas to gas` | `costs.at["biogas", "efficiency"]` |
| `add_biomass()` | `biogas to gas CC` | `costs.at["biogas CC", "efficiency"]` (and `costs.at["biogas", "efficiency"]` for the upgrading component) |

### Technologies confirmed correct (no fix needed)

The following technologies were inspected and already had the correct `× efficiency` pattern:
- `OCGT methanol` (already `costs.at["OCGT", "efficiency"] * costs.at["OCGT", "VOM"]`)
- `allam gas` (already `costs.at["allam", "efficiency"] * costs.at["allam", "VOM"]`)
- `BtL` Fischer-Tropsch variants (already `costs.at["BtL", "efficiency"] * costs.at["BtL", "VOM"]`)
- `Haber-Bosch` (uses `VOM / electricity-input` — equivalent correct pattern)

### Notes

- The `costs_processed.csv` file (output of `process_cost_data.py`) does **not** pre-multiply `VOM` by efficiency. It computes a `marginal_cost` column (`VOM + fuel/η`) intended for Generators, leaving `VOM` untouched. Therefore, the fix must be applied in the network-building scripts, not in `process_cost_data.py`.
- The `biogas upgrading` VOM is nominally per MWh output, and `biogas.efficiency = 1.0` per the cost database, so the fix is numerically neutral for the current dataset but is applied for defensive correctness.
