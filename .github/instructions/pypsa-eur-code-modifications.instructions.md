# PyPSA-Eur Code Modifications

This file documents all modifications made to the original PyPSA-Eur codebase in the context of the GHGP project. Each entry includes a description of the bug or motivation, the affected files and locations, and the exact change applied. This is intended to facilitate upstreaming of fixes to the PyPSA-Eur repository.

---

## 1. `fixed_year` bug in `build_electricity_demand.py` when snapshots cover less than a full year

### Background

The `load.fixed_year` config option allows the user to use the electricity demand of a specific historical year (e.g., 2024) while the model snapshots are anchored to a different year (e.g., 2013, determined by the cutout). This is useful for backcasting runs where the cutout year differs from the demand year.

### Bug

The original code had two bugs that manifested when `fixed_year` was set and snapshots covered less than a full year (e.g., one month):

**Bug 1 — `reindex` before year remapping:**
```python
load = load.loc[years].reindex(index=snapshots)  # reindex with 2013 timestamps on a 2024 index → all NaN
if fixed_year:
    load.index = load.index.map(...)              # too late, DataFrame is already empty
```
`load.loc[years]` has a 2024 index, but `reindex(index=snapshots)` looks for 2013 timestamps → all NaN.

**Bug 2 — Leap day `ValueError` when `fixed_year` is a leap year:**
Even after fixing the order, extracting the full `fixed_year` with `load.loc["2024":"2024"]` includes `2024-02-29`. Remapping with `.map(lambda t: t.replace(year=2013))` then raises `ValueError: day is out of range for month` because 2013 is not a leap year.

### Fix

Invert the mapping direction: instead of extracting the full `fixed_year` and remapping its index to the snapshot year, map the snapshots forward to `fixed_year` to select only the required time slice directly.

**Original code:**
```python
fixed_year = snakemake.params["load"].get("fixed_year", False)
years = (
    slice(str(fixed_year), str(fixed_year))
    if fixed_year
    else slice(snapshots[0], snapshots[-1])
)

load = load.loc[years].reindex(index=snapshots)

# need to reindex load time series to target year
if fixed_year:
    load.index = load.index.map(lambda t: t.replace(year=snapshots.year[0]))

load.to_csv(snakemake.output[0])
```

**Fixed code:**
```python
fixed_year = snakemake.params["load"].get("fixed_year", False)
if fixed_year:
    # Map snapshots to fixed_year to select only the matching time slice.
    # This avoids issues when snapshots cover less than a full year (e.g.
    # one month) and when fixed_year is a leap year (e.g. 2024-02-29 would be skipped).
    fixed_year_index = snapshots.map(lambda t: t.replace(year=int(fixed_year)))
    load = load.loc[fixed_year_index]
    load.index = snapshots
else:
    load = load.loc[slice(snapshots[0], snapshots[-1])].reindex(index=snapshots)

load.to_csv(snakemake.output[0])
```

### Affected files and locations

| File | Function / location | Change |
|---|---|---|
| `scripts/build_electricity_demand.py` | End of `__main__` block, final load selection | Replaced `loc[years].reindex` + `map(replace year)` pattern with inverted mapping via `fixed_year_index` |

### Notes

- The fix is backward-compatible: when `fixed_year=False`, the `else` branch reproduces the original behavior exactly.
- The fix also handles the case of a full-year snapshot with a leap `fixed_year`: since snapshots anchored to a non-leap year (e.g., 2013) never contain Feb 29, `fixed_year_index` will never contain `fixed_year-02-29`, so the leap day is naturally skipped — consistent with `drop_leap_day: true`.

---

## 2. VOM unit conversion bug in Link `marginal_cost`

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

---

## 3. Biomass double-representation when `sector.biomass: false`

### Background

In myopic mode, bioenergy plants from PowerPlantMatching (PPM) flow through two separate pipelines:

1. **`add_electricity.py`** (`attach_conventional_generators()`): PPM `"Bioenergy"` fueltype → `Generator` with `carrier="biomass"`, `p_nom` in MW_el, marginal cost from costs database.
2. **`add_existing_baseyear.py`** (`add_power_capacities_installed_before_baseyear()`): same PPM plants → `Link` with `carrier="urban central solid biomass CHP"`, `p_nom` in MW_fuel, `bus0` pointing to `"<node> solid biomass"` buses.

When `sector.biomass: true`, `prepare_sector_network.py` calls `add_biomass()` which (a) creates the `"EU solid biomass"` fuel buses and (b) `remove_elec_base_techs()` drops the biomass Generators (because `biomass` is absent from the default `pypsa_eur.Generator` list). The two pipelines therefore produce a single correct representation.

### Bug

This bug is specific to the combination of **`sector.biomass: false`** and **`biomass` included in `pypsa_eur.Generator`** — which is the GHGP project configuration.

When `sector.biomass: false`, `add_biomass()` is never called:
- The `"EU solid biomass"` buses are never created.
- `remove_elec_base_techs()` is called but **keeps** the biomass Generators, because `biomass` is explicitly listed in `pypsa_eur.Generator` in `config.rmi.yaml`.
- **Despite this**, `add_existing_baseyear.py` still added the CHP Links unconditionally. It created the missing `"<node> solid biomass"` buses on-the-fly, added the Links with `bus0` pointing to those phantom buses, and left no `Generator` providing energy to that bus.

This caused two problems simultaneously:
1. **Double-counting**: both Generators (~MW_el from PPM) and Links (~same capacity as MW_el equivalent) representing the same physical plants.
2. **Free fuel**: the phantom `bus0` bus had no supply (no `Generator` or `Store`), so its energy balance was unconstrained — biomass fuel was effectively free.

**Without `biomass` in `pypsa_eur.Generator`** (PyPSA-Eur default): `remove_elec_base_techs()` would drop the Generators, so only the Links would remain. The double-counting would not occur, but the free-fuel problem would still be present (phantom bus with no supply). The fix addresses both configurations.

### Fix

Added an `options` parameter to `add_power_capacities_installed_before_baseyear()` and a guard that skips the biomass CHP Link creation when `sector.biomass: false`:

```python
# scripts/add_existing_baseyear.py
# in the else branch of the generator loop, before bus0 computation and bus creation:
if generator == "urban central solid biomass CHP" and not options.get("biomass", False):
    continue  # biomass buses not created; plants already in network as Generators
```

### Affected files and locations

| File | Change |
|---|---|
| `scripts/add_existing_baseyear.py` | Added `options: dict` parameter to `add_power_capacities_installed_before_baseyear()` |
| `scripts/add_existing_baseyear.py` | Added `continue` guard skipping biomass CHP Links when `options["biomass"]` is `False` |
| `scripts/add_existing_baseyear.py` | Passed `options=options` at the call site in `__main__` |

### When `sector.biomass: true`

When `sector.biomass: true`, `options["biomass"]` is `True`, the guard is not triggered, and the original behaviour is preserved: `add_biomass()` creates the fuel buses, `remove_elec_base_techs()` drops the Generators, and the Links are added as before.

### Notes

- The fix is **backward-compatible**: the function signature has `options: dict` as a required parameter. All existing call sites in the codebase that use `sector.biomass: true` pass `options` (now made explicit) and are unaffected.
- The double-counting and free-fuel issues were silent: PyPSA did not warn about the phantom buses. The only observable symptom was anomalously high biomass dispatch and incorrect installed capacity totals.
- The `continue` guard is placed **before** the `bus0` computation and phantom bus creation block, so when `sector.biomass: false` no spurious buses are added to the network at all.
