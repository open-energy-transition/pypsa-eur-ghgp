# Calibration

This section includes all the changes applied to the [upstream PyPSA-EUR](https://github.com/open-energy-transition/pypsa-eur) scripts. These changes addresses calibration issues that have been faced while developing the model and adapting it to simulate the historical period 2020-2025. These issues can be classifed in two categories:

* **Data availability:** some default input data are not available for recent past years (e.g., 2024 and 2025).
* **Calibration:** resulting default existing capacities for some carriers in past year are not aligned with historical data.

Details and examples of such issues, alongside the solutions implemented in the project to partially overcome them, are provided below.

!!! note
    This is not meant to be a comprehensive description of the calibration needs of PyPSA-Eur, as it is based on this specific project. Also, the latter did not involve any direct calibration activities. Instead, the description below is meant to be a starting point to investigate whether, and to which extent, further calibrating PyPSA-Eur might be useful for the PyPSA-EURcommunity. In this regard, the topic has been raised in the [discord server](https://discord.com/invite/AnuJBk23FU).

---

## Data availability
### 1) Synthetic load data
**Availability**: **until 2023 (included)** ==> if snapshots year > 2023, a `KeyError` is raised.

**Script/function**: [`build_electricity_demand.py`](https://github.com/PyPSA/pypsa-eur/blob/1f8d4a503ac9b348072cca9a6446926b452c091f/scripts/build_electricity_demand.py#L312-L316).

**Upstream code**:
```python
synthetic_load = pd.read_csv(fn, index_col=0, parse_dates=True)
countries = list(set(countries) - set(["UA", "MD", "XK", "CY", "MT"]))
synthetic_load = synthetic_load.loc[snapshots, countries] # ← KeyError when snapshots > 2023
load = load.combine_first(synthetic_load)
```
This code would generate this error:
> raise KeyError(f"None of [{key}] are in the [{axis_name}]")

**New code**:
```python
synthetic_load = pd.read_csv(fn, index_col=0, parse_dates=True)
countries = list(set(countries) - set(["UA", "MD", "XK", "CY", "MT"]))
available_snapshots = synthetic_load.index.intersection(snapshots)
if available_snapshots.empty:
    logger.warning(
        "Synthetic load data does not cover the requested snapshots "
        f"({snapshots[0]} – {snapshots[-1]}). Skipping supplement step."
    )
else:
    if len(available_snapshots) < len(snapshots):
        missing = len(snapshots) - len(available_snapshots)
        logger.warning(
            f"Synthetic load data covers only {len(available_snapshots)}/{len(snapshots)} "
            f"snapshots ({missing} timestamps missing, will not be supplemented)."
        )
    synthetic_load = synthetic_load.loc[available_snapshots, countries]
    load = load.combine_first(synthetic_load)
```

### 2) JRC IDEES
**Availability**: **until 2023 (included)** ==> if snapshots year > 2023, a `KeyError` is raised only for the heating sector.

**Script/function**: [`build_population_weighted_energy_totals.py`](https://github.com/PyPSA/pypsa-eur/blob/1f8d4a503ac9b348072cca9a6446926b452c091f/scripts/build_population_weighted_energy_totals.py#L32-L43).

**Upstream code**:
```python
if snakemake.wildcards.kind == "heat":
    snapshots = get_snapshots(
        snakemake.params.snapshots, snakemake.params.drop_leap_day
    )
    data_years = snapshots.year.unique()
else:
    data_years = int(config["energy_totals_year"])

pop_layout = pd.read_csv(snakemake.input.clustered_pop_layout, index_col=0)

totals = pd.read_csv(snakemake.input.energy_totals, index_col=[0, 1])

totals = totals.loc[idx[:, data_years], :].groupby("country").mean() # ← KeyError when snapshots > 2023
```
This code would generate this error:
> raise KeyError(key) from err

**New code**: substitute the code above with:
```python
if snakemake.wildcards.kind == "heat":
    snapshots = get_snapshots(
        snakemake.params.snapshots, snakemake.params.drop_leap_day
    )
    data_years = snapshots.year.unique()
else:
    data_years = int(config["energy_totals_year"])

pop_layout = pd.read_csv(snakemake.input.clustered_pop_layout, index_col=0)

totals = pd.read_csv(snakemake.input.energy_totals, index_col=[0, 1])

if snakemake.wildcards.kind == "heat":
    available_years = totals.index.get_level_values(1).unique()
    data_years = data_years[pd.Series(data_years).isin(available_years).values]
    if len(data_years) == 0:
        data_years = int(config["energy_totals_year"])
        logger.warning(
            f"Snapshot years not found in energy totals data. "
            f"Falling back to energy_totals_year={data_years}."
        )

totals = totals.loc[idx[:, data_years], :].groupby("country").mean()
```

### 3) Nuclear `p_max_pu`
**Availability**: **until 2024 (included)** ==> if snapshots year > 2024, a `KeyError` is raised.

**Script/function**: [`add_electricity.py/attach_conventional_generators()`](https://github.com/PyPSA/pypsa-eur/blob/1f8d4a503ac9b348072cca9a6446926b452c091f/scripts/add_electricity.py#L682-L687).

**Upstream code**:
```python
try:
    df.columns = df.columns.astype(int)
    year = n.snapshots[0].year
    values = df[year]          # ← KeyError when snapshots > 2024
except (ValueError, TypeError):
    values = df.iloc[:, -1] 
```
This code would generate this error:
> raise KeyError(key) from err

**New code**:
```python
try:
    df.columns = df.columns.astype(int)
    year = n.snapshots[0].year
    year = min(year, df.columns.max())
    values = df[year]
except (ValueError, TypeError):
    values = df.iloc[:, -1]
```

---

## Calibration
### 1) IRENASTAT existing capacities
**Issue**: existing capacities added in years > calibration year are accounted for when considering existing solar and wind capacities.

**Script/function**: [`add_existing_baseyear.py/add_existing_renewables()`](https://github.com/PyPSA/pypsa-eur/blob/1f8d4a503ac9b348072cca9a6446926b452c091f/scripts/add_existing_baseyear.py#L71).

**Example**: calibration year=2023, carrier=`solar`, country=`DE`
When analyzing the network `n` after `add_existing_baseyear`:
```python
n.generators[(n.generators.index.str.contains("DE")) & (n.generators.carrier=="solar")].p_nom.sum()/1e3
> np.float64(89.943)
```
I would get ~ 90 GW against historical ~ 77 GW from [EnergyCharts](https://www.energy-charts.info/charts/installed_power/chart.htm?l=en&c=DE&year=2023).

In particular, when looking at the `build_year`:
```python
n.generators[(n.generators.index.str.contains("DE")) & (n.generators.carrier=="solar")].build_year.unique()
> array([2023, 2000, 2005, 2010, 2015, 2020, 2025])
```

**Implemented solution**: filter IRENASTAT data up to the calibration year (i.e., `baseyear`), by adding before this [line](https://github.com/PyPSA/pypsa-eur/blob/1f8d4a503ac9b348072cca9a6446926b452c091f/scripts/add_existing_baseyear.py#L118) (i.e., `df.insert(loc=0, value=0.0, column="1999")`, the following:
```python
df = df.loc[:, df.columns <= baseyear]
```

When doing so:
```python
n.generators[(n.generators.index.str.contains("DE")) & (n.generators.carrier=="solar")].p_nom.sum()/1e3
>np.float64(74.882)

n.generators[(n.generators.index.str.contains("DE")) & (n.generators.carrier=="solar")].build_year.unique()
>array([2023, 2000, 2005, 2010, 2015, 2020])
```

### 2) Other existing capacities
**Issue**: underestimation of actual existing capacities for those power plants from PPM dataset, with unkonwn `DateOut`. In this case, the latter is estimated by using the `lifetime` from the technology costs dataset:  if the estimated `DateOut < baseyear`, those power plants are filtered out, even though they might be still operating in the `baseyear`.

**Script/function**: [`add_existing_baseyear.py/add_power_capacities_installed_before_baseyear()](https://github.com/PyPSA/pypsa-eur/blob/f124355cfa4987dbab3335dbdb22aa6de57b3ff6/scripts/add_existing_baseyear.py#L153).

In particular:
```python
[...]

# Estimate missing DateOut
df_agg["DateOut"] = df_agg.DateOut.combine_first(
    df_agg.DateIn + df_agg.Fueltype.map(costs.lifetime).fillna(30)
)

[...]

# drop assets which are already phased out / decommissioned
phased_out = df_agg[df_agg["DateOut"] < baseyear].index
df_agg.drop(phased_out, inplace=True)

[...]
```

**Potential solution**: this issue has not been addressed in the project. However, a preliminary solution might be to estimate an average lifetime by carrier and by `DateIn`, which is different from the fixed technology cost one.
