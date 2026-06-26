# Other minor code changes

This section includes all the other modifications applied to the [upstream PyPSA-EUR](https://github.com/open-energy-transition/pypsa-eur) scripts. These are minor code changes not directly related to model calibration, but needed to correctly run the scenarios with the configuration settings described in section [Configuration](configuration.md).

---

## Modeling of existing biomass power plants when `sector.biomass: false`
**Script/function:** [`scripts/add_existing_baseyear.py/add_power_capacities_installed_before_baseyear()`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/scripts/add_existing_baseyear.py#L162).

**Issue:**

This bug is due to the combination of the project configuration settings `sector.biomass: false` and `biomass` included in `pypsa_eur.Generator`. The former is needed as the model is limited to the electricity sector only, with the aim not to model biomas-related technologies, including biomass CHP as links. Instead, the latter guarantees to keep the existing biomass power plants (including the CHP ones) as generators. If this is the case:

- `add_biomass()` is never called in [`scripts/prepare_sector_network.py`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/scripts/prepare_sector_network.py), so that the `"EU solid biomass"` buses (i.e., the `bus0` of CHP links) are never created.
- **despite this**, `add_existing_baseyear.py` would still add the CHP links unconditionally. It would create the missing `"<node> solid biomass"` buses, add the links with `bus0` pointing to those phantom buses, and left no `Generator` providing energy to that bus.

This would cause two problems simultaneously:

1. **Double-counting**: both generators and links representing the same physical plants.
2. **Free fuel**: the phantom `bus0` bus would not have supply (no `Generator` or `Store`), so its energy balance would be unconstrained (i.e., biomass fuel was effectively free).

Without `biomass` in `pypsa_eur.Generator` (PyPSA-Eur default setting), `remove_elec_base_techs()` would drop the generators in [`scripts/prepare_sector_networ.py`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/scripts/prepare_sector_network.py), so only the links would remain. The double-counting would not occur, but the free-fuel problem would still be present (phantom bus with no supply). The implemented fix addresses both the problems.

**New code:**

```python
# scripts/add_existing_baseyear.py/add_power_capacities_installed_before_baseyear()
# in the else branch of the generator loop, before bus0 computation and bus creation:
if generator == "urban central solid biomass CHP" and not options.get("biomass", False):
    continue  # biomass buses not created; plants already in network as Generators
```

---

## Modeling of existing nuclear power plants
**Script/function:** [`scripts/add_existing_baseyear.py/add_power_capacities_installed_before_baseyear()`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/scripts/add_existing_baseyear.py#L162).

**Issue:**

In myopic mode, nuclear power plants are represented both as generators and as links (from add_existing_baseyear.py), but the link is always idle (i.e., no dispatch) because the `EU uranium` bus has no supply. This would leads to double-counting in existing capacity statistics, as for the first problem about biomass power plants described above.

**New code:**
```python
# scripts/add_existing_baseyear.py/add_power_capacities_installed_before_baseyear()
# in the else branch of the generator loop, before bus0 computation and bus creation:
if generator == "nuclear":
    continue
```

**Notes:**

This is a well-know bug in the [original PyPSA-Eur](https://github.com/PyPSA/pypsa-eur), which is currently being addresed in [this PR](https://github.com/PyPSA/pypsa-eur/pull/1540).

---

## Electricity demand processing when load year differs from snapshots
**Script/function:** [`scripts/build_electricity_demand.py`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/scripts/build_electricity_demand.py).

**Issue:**

A `load.fixed_year` different from the snapshot year (i.e., the weather year) implies no timestamp match when building the electricity demand, so that the entire load data frame becomes `NaN`.

**Upstream code:**
```python
fixed_year = snakemake.params["load"].get("fixed_year", False)
years = (
    slice(str(fixed_year), str(fixed_year))
    if fixed_year
    else slice(snapshots[0], snapshots[-1])
)

load = load.loc[years].reindex(index=snapshots) #!!! reindex with snapshot timestamps on a different load year index → all NaN

if fixed_year:
    load.index = load.index.map(lambda t: t.replace(year=snapshots.year[0])) #!!! too late, DataFrame is already empty

load.to_csv(snakemake.output[0])
```

**New code:**
```python
fixed_year = snakemake.params["load"].get("fixed_year", False)
if fixed_year:
    fixed_year_index = snapshots.map(lambda t: t.replace(year=int(fixed_year)))
    load = load.loc[fixed_year_index]
    load.index = snapshots
else:
    load = load.loc[slice(snapshots[0], snapshots[-1])].reindex(index=snapshots)

load.to_csv(snakemake.output[0])
```

**Notes:**

- Consider that this bug was faced when testing the model with different load and weather years. However, the final full model configuration provides for the same load and weather year, so that the bug would not be faced.
- The fix is backward-compatible: when `load.fixed_year: false`, the `else` branch reproduces the original behavior exactly. However, the fix does not handle the case when load year differ from snapshots, the former is not a leap year, whereas the latter is a leap year. In this regard, the code line `fixed_year_index = snapshots.map(lambda t: t.replace(year=int(fixed_year)))` would raise this error: `ValueError: day is out of range for month.` In this regard, a more comprehensive [bug issue](https://github.com/PyPSA/pypsa-eur/issues/2187) has been raised in the [original PyPSA-Eur](https://github.com/PyPSA/pypsa-eur) repository.