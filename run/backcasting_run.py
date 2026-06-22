# SPDX-FileCopyrightText: Open Energy Transition gGmbH and contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""
Interactive runner for GHGP backcasting scenarios.

Usage (from the repository root):
        python run/backcasting_run.py

This script reads available scenarios from config/scenarios.rmi.yaml,
allows the user to select one or more scenarios (by year or name), and runs
`snakemake solve_sector_networks` for each using:

        snakemake --configfile BASE_CONFIG --config 'run={name: <scenario>}'

This ensures that Snakemake performs all config merging natively—
scenarios.enable remains true, dynamic_getter is used, and metadata from prior direct runs is always recognized as up-to-date.

Resource sharing
----------------
- The `data/` directory is always shared (contains static datasets, never written by Snakemake).
- The `resources/` directory uses `policy: false`—each scenario has its own subfolder `resources/{scenario_name}/`.
    Using `policy: "base"` is not possible in myopic mode (due to path mismatches between producer and consumer of costs_processed.csv).

Two symlink strategies are applied automatically:

1. Baseline → baseline (cross-year): symlink only year-INDEPENDENT files.
     Many resource files (cutout profiles, geographic shapes, OSM network,
     busmap, etc.) do not depend on the backcasting year and are identical
     across all baseline scenarios. The reference is always the baseline-2025
     scenario (detected automatically from the scenarios file).

     Year-independent files (safe to symlink):
         - availability_matrix_{clusters}_{tech}.nc  (spatial mask only — atlite uses the
           cutout grid geometry, not temporal data; all cutout years share the same domain)
         - regions_*.geojson / *_shapes.geojson
         - networks/base*.nc   (OSM network, before electricity)
         - busmap, linemap, pop_layout_{total,urban,rural}.nc, pop_layout_base_s_{c}.csv
           (pop_layout uses cutout.indicatormatrix() — spatial only)

     Year-dependent files (always recomputed, never symlinked cross-year):
         - profile_{clusters}_{tech}.nc / profile_hydro.nc        (cutout-derived time series)
         - regions_by_class_{clusters}_{tech}.geojson             (cutout-derived resource classes;
                                                                   year-independent with
                                                                   resource_classes=1 but marked
                                                                   defensively)
         - solar_rooftop_potentials_s_{clusters}.csv              (depends on regions_by_class_;
                                                                   symlink would be immediately
                                                                   overwritten by Snakemake anyway)
         - temp_soil_* / temp_air_* / daily_heat_demand_* /       (cutout-derived; not produced
           hourly_heat_demand_* / solar_thermal_*                  when heating=false but marked
                                                                   defensively)
         - electricity_demand.csv / electricity_demand_base_s.nc  (depends on load.fixed_year)
         - powerplants_s_{clusters}.csv                           (depends on powerplants_filter)
         - costs_{year}_processed.csv                             (year in filename)
         - networks/base_s_{clusters}_elec*.nc                    (depends on above)
         - any file matching _20XX in its name                    (year in filename)
         - pop_weighted_{energy,heat}_totals_s_{c}.csv            (depends on energy.energy_totals_year)
         - shipping_demand_s_{c}.csv                              (depends on energy.energy_totals_year)
         - transport_demand_s_{c}.csv / transport_data_s_{c}.csv  (depends on energy.energy_totals_year)
         - avail_profile_s_{c}.csv / dsm_profile_s_{c}.csv        (depends on energy.energy_totals_year)

2. Baseline → project (same year): symlink ALL resource files.
     A project scenario (e.g. test-project-2024-3H-1M-DE-solar-100MW) shares
     every config key with its same-year baseline (test-baseline-2024-3H-1M-DE):
     planning_horizons, powerplants_filter, fixed_year, costs.year,
     energy_totals_year, biomass, existing_capacities. Therefore, ALL resources
     up to and including *_brownfield.nc are identical. Only two rules need
     to run for a project scenario:
         - add_project_generators  (produces *_brownfield_project.nc)
         - solve_sector_network_myopic
     The file *_brownfield_project.nc is excluded from the symlinks (it is the
     output that add_project_generators must create).

     Detection is automatic from the scenario name: if "project" is in the name,
     the script extracts the year and looks for the matching baseline in the
     scenarios list. No CLI flag is needed.
"""

import os
import re
from pathlib import Path

import yaml

SNAKEMAKE_TARGET = "solve_sector_networks"

_CONFIGS = [
    (
        "config/config.rmi.yaml",
        "config/scenarios.rmi.yaml",
        "Full model (config.rmi.yaml)",
    ),
    (
        "config/test/config.rmi.DE.yaml",
        "config/test/scenarios.rmi.DE.yaml",
        "DE test model (config.rmi.DE.yaml)",
    ),
]

# Matches _20XX (year 20xx) as a name segment: _2025, _2025_, or _2025 at end
_YEAR_RE = re.compile(r"_20\d{2}([._]|$)")

# Files that are filtered by energy.energy_totals_year inside each script.
# energy_totals.csv itself contains ALL years; downstream scripts extract a
# single year, so their outputs differ between the 2020 scenario (year=2020) and
# the 2024/2025/project scenarios (year=2023). Never symlink these.
_ENERGY_YEAR_PREFIXES = (
    # build_population_weighted_energy_totals (filters energy_totals to energy_totals_year)
    "pop_weighted_energy_totals_s_",
    "pop_weighted_heat_totals_s_",
    # build_shipping_demand (demand.xs(energy_totals_year, level=1))
    "shipping_demand_s_",
    # build_transport_demand (uses energy_totals_year throughout)
    "transport_demand_s_",
    "transport_data_s_",
    "avail_profile_s_",
    "dsm_profile_s_",
)


# ---------------------- Resource sharing helpers ----------------------


def _find_reference_scenario(scenario_list: list[str]) -> str | None:
    """
    Return the baseline-2025 scenario name to use as the symlink reference.

    The 2025 baseline is the unique correct choice because it maximises the set
    of year-independent files that can be safely symlinked to other scenarios:

    Year-INDEPENDENT files (identical across all backcasting years, safe to symlink):
        - availability_matrix_{clusters}_{tech}.nc — spatial mask only; atlite uses
          the cutout purely for its grid geometry (x/y coordinates), not for any
          temporal weather data. All cutout years share the same domain
          (x[-12,42] y[33,72] dx=dy=0.3), so the matrix is identical across years.
        - Geographic shapes, regions, busmaps, linemaps — derived from the
          OSM network snapshot (Feb 2026) and the clustering algorithm,
          neither of which depends on the backcasting year
        - Base network (networks/base*.nc) — OSM topology, year-invariant
        - pop_layout_{total,urban,rural}.nc — NUTS3 population regridded to cutout
          grid; pop_layout_base_s_{c}.csv — clustered population. Both use
          cutout.indicatormatrix() (spatial only), year-invariant.

    Year-DEPENDENT files (differ across backcasting years, never symlinked):
        - profile_{clusters}_{tech}.nc / profile_hydro.nc — computed from the
          per-horizon atlite cutout (europe-{year}-sarah3-era5); hourly capacity
          factors change with the actual weather of each year
        - regions_by_class_{clusters}_{tech}.geojson — resource quality classes
          derived from the same cutout; content is year-independent with
          resource_classes=1 (default) but marked defensively since
          build_renewable_profiles runs anyway
        - solar_rooftop_potentials_s_{clusters}.csv — depends on regions_by_class_;
          symlink would be overwritten by Snakemake (input newer than output)
        - temp_soil_* / temp_air_* / daily_heat_demand_* / hourly_heat_demand_* /
          solar_thermal_* — hourly time series extracted from the cutout
          (not produced now because heating=false, but marked defensively)
        - powerplants_s_{clusters}.csv — filtered by powerplants_filter (DateIn/DateOut)
        - electricity_demand.csv / electricity_demand_base_s.nc — filtered by load.fixed_year
        - costs_{year}_processed.csv — year encoded in filename
        - networks/base_s_{clusters}_elec*.nc — depends on powerplants and costs
        - IRENASTAT-derived capacities inside *_brownfield.nc — add_existing_baseyear
          uses all IRENASTAT columns up to planning_horizons[0], so the brownfield
          network differs between years
        - pop_weighted_*_totals, shipping_demand, transport_* — filtered by
          energy_totals_year (2020 for Y=2020; 2023 for Y=2021-2025)

    Why 2025 specifically:
        - It is the latest year, so its IRENASTAT snapshot is the most inclusive;
          earlier baselines always have a strict subset of its renewable vintages
        - energy_totals_year is capped at 2023 for Y≥2021 (JRC IDEES data
          constraint), so 2021-2025 baselines all share the same energy_totals_year
        - 2020 must never be used as reference: it uses energy_totals_year=2020,
          making its pop_weighted_* and shipping_demand files incompatible with
          all other baselines

    Detection is by name: finds the first scenario containing both 'baseline'
    and '2025', so it works regardless of prefix or temporal-resolution suffix.
    """
    for s in scenario_list:
        if "baseline" in s and "2025" in s:
            return s
    return None


def _is_year_dependent(rel_posix: str) -> bool:
    """
    Return True if this resource file varies across backcasting years.
    Used to determine if a file is safe to symlink between baselines of different years.
    """
    name = Path(rel_posix).name
    # Has a year segment in the filename (e.g. costs_2025_processed.csv)
    if _YEAR_RE.search(name):
        return True
    # electricity demand depends on load.fixed_year (no year in filename)
    if name in {"electricity_demand.csv", "electricity_demand_base_s.nc"}:
        return True
    # powerplants_s_{clusters}.csv depends on powerplants_filter
    if name.startswith("powerplants_s_") and name.endswith(".csv"):
        return True
    # Electricity networks depend on powerplants and costs
    if rel_posix.startswith("networks/") and "_elec" in name:
        return True
    # Files filtered by energy.energy_totals_year inside the producing script.
    # Note: energy_totals.csv itself is multi-year and year-independent; only
    # the downstream scripts extract a single year, making their outputs vary
    # between energy_totals_year=2020 and =2023.
    if name.startswith(_ENERGY_YEAR_PREFIXES):
        return True
    # Cutout-derived time-series files: built from atlite cutouts that are now
    # per-planning-horizon (europe-{year}-sarah3-era5). The weather data differs
    # between years, so these outputs must be recomputed for every baseline year.
    #
    # Renewable generation profiles (build_renewable_profiles, build_hydro_profile):
    #   - profile_{clusters}_{tech}.nc
    #   - profile_hydro.nc
    #   - regions_by_class_{clusters}_{tech}.geojson  (resource quality classes)
    #       With resource_classes=1 (default/RMI) the content is year-independent
    #       (nbins==1 → class_regions = resource_regions, no CF binning). Marked
    #       year-dependent defensively: build_renewable_profiles runs anyway for
    #       profile_*.nc, and the co-output regions_by_class_* should match it.
    if name.startswith("profile_"):
        return True
    if name.startswith("regions_by_class_"):
        return True
    # Solar rooftop potentials: produced by build_clustered_solar_rooftop_potentials
    # which uses regions_by_class_{clusters}_solar.geojson as input. Since that
    # file is not symlinked (year-dependent above), build_renewable_profiles will
    # produce a fresh regions_by_class_* with a newer timestamp, causing Snakemake
    # to rerun build_clustered_solar_rooftop_potentials regardless. Marking this
    # file year-dependent avoids creating a symlink that will be immediately
    # overwritten.
    #   - solar_rooftop_potentials_s_{clusters}.csv
    if name.startswith("solar_rooftop_potentials_s_"):
        return True
    # Sector-coupling heat/temperature profiles (build_temperature_profiles,
    # build_daily_heat_demand, build_solar_thermal_profiles, etc.).
    # Currently not produced because sector.heating=false in the RMI config,
    # but marked here defensively so they are never incorrectly symlinked if
    # heating is ever enabled.
    #   - temp_soil_total_base_s_{clusters}.nc
    #   - temp_air_total_base_s_{clusters}.nc
    #   - temp_ambient_air_base_s_{clusters}_temporal_aggregate.nc
    #   - daily_heat_demand_total_base_s_{clusters}.nc
    #   - hourly_heat_demand_total_base_s_{clusters}.nc
    #   - residential_heat_dsm_profile_total_base_s_{clusters}.csv
    #   - solar_thermal_total_base_s_{clusters}.nc
    if name.startswith(
        (
            "temp_soil_",
            "temp_air_",
            "temp_ambient_air_",
            "daily_heat_demand_",
            "hourly_heat_demand_",
            "residential_heat_dsm_profile_",
            "solar_thermal_",
        )
    ):
        return True
    return False


def _find_reference_resources(scenario_name: str | None) -> Path | None:
    """
    Return the baseline-2025 resources folder if it already exists.
    Used as the source for symlinking year-independent files across baselines.
    """
    if scenario_name is None:
        return None
    ref = Path("resources") / scenario_name
    return ref if ref.is_dir() else None


def _is_project_scenario(scenario_name: str) -> bool:
    """
    Return True if this is a project scenario (contains 'project' in the name).
    Project scenarios require a different symlink strategy.
    """
    return "project" in scenario_name


def _find_same_year_baseline(
    scenario_name: str, scenario_list: list[str]
) -> str | None:
    """
    For a project scenario, find the corresponding same-year baseline.

    Extracts the first 4-digit year found in the scenario name and looks for
    a baseline scenario containing the same year. Returns the baseline name or None.
    """
    m = re.search(r"(\d{4})", scenario_name)
    if not m:
        return None
    year = m.group(1)
    for s in scenario_list:
        if "baseline" in s and year in s:
            return s
    return None


def symlink_shared_resources(
    reference_dir: Path,
    target_dir: Path,
    all_files: bool = False,
) -> list[Path]:
    """
    Symlink resource files from reference_dir into target_dir.

    Parameters
    ----------
    reference_dir:
        Folder to copy symlinks from.
    target_dir:
        Folder to create symlinks in.
    all_files:
        If False (default), skip year-dependent files (cross-year baseline strategy).
        If True, symlink ALL files except *_brownfield_project.nc (same-year
        baseline→project strategy).

    Snakemake will see the symlinked outputs as already produced and skip
    the corresponding rules, avoiding redundant computation.
    Returns the list of symlink paths created.
    """
    created: list[Path] = []
    for src in sorted(reference_dir.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(reference_dir)
        rel_posix = rel.as_posix()
        name = Path(rel_posix).name

        if all_files:
            # Same-year baseline→project: skip only the brownfield_project output,
            # which add_project_generators must produce fresh for this scenario.
            if "_brownfield_project" in name:
                continue
        else:
            # Cross-year: skip year-dependent files.
            if _is_year_dependent(rel_posix):
                continue

        dst = target_dir / rel
        if dst.exists() or dst.is_symlink():
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(src.resolve())
        created.append(dst)
    return created


# ---------------------- Utility Functions ----------------------


def select_scenarios(scenario_list):
    """
    Let the user select one or more scenarios from the list.

    Enter 0 or 'all' to select all available scenarios.
    Enter a single number/name or a comma-separated list for multiple selections.
    Press Enter without input to cancel.
    """
    print("Available backcasting scenarios:")
    print("  0. all")
    for i, name in enumerate(scenario_list, 1):
        print(f"  {i}. {name}")
    print("(Enter 0 or 'all' to run every scenario.)")
    print("(Enter numbers or names, comma-separated for multiple.)")
    print("(Press Enter without input to cancel.)")

    while True:
        answer = input("Select scenario(s): ").strip()
        if not answer:
            return None

        # "all" shortcut
        if answer in ("0", "all"):
            print("\nAll scenarios selected:")
            for s in scenario_list:
                print(f"  - {s}")
            return list(scenario_list)

        tokens = [t.strip() for t in answer.split(",")]
        selected = []
        valid = True
        for token in tokens:
            if token.isdigit():
                idx = int(token) - 1
                if 0 <= idx < len(scenario_list):
                    selected.append(scenario_list[idx])
                else:
                    print(f"  '{token}' is out of range. Please try again.")
                    valid = False
                    break
            elif token in scenario_list:
                selected.append(token)
            else:
                print(f"  '{token}' not found. Please try again.")
                valid = False
                break

        if valid and selected:
            # Deduplicate while preserving order
            seen = set()
            selected = [s for s in selected if not (s in seen or seen.add(s))]
            print("\nSelected scenarios:")
            for s in selected:
                print(f"  - {s}")
            return selected


def select_cpus():
    """Ask how many local CPUs to use for Snakemake runs."""
    while True:
        cpu = input("\nHow many CPUs to use (all or a number)? ").strip().lower()
        if not cpu:
            return None
        if cpu == "all":
            return "-call"
        if cpu.isdigit() and int(cpu) > 0:
            return f"-c{cpu}"
        print(f"  '{cpu}' is not valid. Please enter 'all' or a positive number.")


def select_config() -> tuple[str, str]:
    """Ask the user which config/scenarios pair to use."""
    print("\nAvailable configurations:")
    for i, (cfg, scen, label) in enumerate(_CONFIGS, 1):
        print(f"  {i}. {label}")
        print(f"       config:    {cfg}")
        print(f"       scenarios: {scen}")
    while True:
        answer = input("Select configuration [1]: ").strip()
        if answer == "" or answer == "1":
            cfg, scen, label = _CONFIGS[0]
            print(f"  → {label}")
            return cfg, scen
        if answer == "2":
            cfg, scen, label = _CONFIGS[1]
            print(f"  → {label}")
            return cfg, scen
        print("  Please enter 1 or 2.")


def select_dry_run_mode() -> bool:
    """Ask whether to do a dry-run and confirmation before each scenario."""
    while True:
        answer = input("\nDry-run before each scenario? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please enter 'y' or 'n'.")


# ---------------------- Main Script ----------------------


def main():
    print("=" * 60)
    print("GHGP Backcasting Run Script")
    print("=" * 60)

    base_config_path, scenarios_file_path = select_config()

    # Load available scenarios
    with open(scenarios_file_path) as f:
        scenarios_config = yaml.safe_load(f)

    # Load base config for fallback values
    with open(base_config_path) as f:
        base_config = yaml.safe_load(f)

    scenario_list = list(scenarios_config.keys())
    reference_scenario = _find_reference_scenario(scenario_list)

    selected_scenarios = select_scenarios(scenario_list)
    if not selected_scenarios:
        print("\nOperation cancelled by user.")
        return

    cores_flag = select_cpus()
    if not cores_flag:
        print("\nOperation cancelled by user.")
        return

    dry_run_mode = select_dry_run_mode()

    print(f"\nCores flag: {cores_flag}")
    print(f"Dry-run mode: {'enabled' if dry_run_mode else 'disabled'}")
    print("=" * 60)

    # Track the first completed scenario folder to use as the symlink reference
    reference_resources: Path | None = _find_reference_resources(reference_scenario)

    # Run each selected scenario
    for scenario_name in selected_scenarios:
        print(f"\nRunning scenario: {scenario_name}")
        print("-" * 60)

        target_resources = Path(f"resources/{scenario_name}")

        # --config overrides run.name and scenario.planning_horizons inside the
        # already-loaded configfile, preserving scenarios.enable:true and the
        # dynamic_getter code path.
        # scenario.planning_horizons must match the per-scenario value so that:
        #   1. solve_sector_networks (collect.smk) expands over the correct year
        #   2. add_existing_baseyear.wildcard_constraints matches the baseyear
        ph = ((scenarios_config.get(scenario_name) or {}).get("scenario") or {}).get(
            "planning_horizons"
        ) or base_config["scenario"]["planning_horizons"]
        config_override = (
            f"'run={{name: {scenario_name}}}' 'scenario={{planning_horizons: {ph}}}'"
        )

        # Symlink strategy:
        #   - Project scenario: symlink ALL resources from the same-year baseline
        #     (only add_project_generators + solve need to run).
        #   - Other scenarios: symlink year-independent files from the baseline-2025 reference.
        # In both cases, run --cleanup-metadata and --touch to ensure metadata is written for symlinked files.
        if _is_project_scenario(scenario_name):
            # Same-year baseline → project: full symlink strategy.
            same_year_baseline = _find_same_year_baseline(scenario_name, scenario_list)
            baseline_resources = (
                Path("resources") / same_year_baseline if same_year_baseline else None
            )
            if baseline_resources is not None and baseline_resources.is_dir():
                symlinked = symlink_shared_resources(
                    baseline_resources, target_resources, all_files=True
                )
                if symlinked:
                    print(
                        f"  Symlinked {len(symlinked)} resources (all files) from "
                        f"same-year baseline '{same_year_baseline}' "
                        f"→ only add_project_generators + solve will run."
                    )
                    files_str = " ".join(str(p) for p in symlinked)
                    cleanup_cmd = (
                        f"snakemake --cleanup-metadata {files_str}"
                        f" --configfile {base_config_path} --config {config_override}"
                    )
                    print("  Cleaning up metadata for symlinked files...")
                    os.system(cleanup_cmd)

                    # Force metadata creation with --touch for all upstream rules
                    # (those that produce the symlinked files)
                    print(
                        "  Forcing metadata: snakemake --touch for all upstream rules..."
                    )
                    touch_cmd = f"snakemake --touch --configfile {base_config_path} --config {config_override}"
                    os.system(touch_cmd)
            else:
                if same_year_baseline:
                    print(
                        f"  Same-year baseline '{same_year_baseline}' not yet computed "
                        f"— running full pipeline for project scenario."
                    )
                else:
                    print(
                        "  No matching same-year baseline found — running full pipeline."
                    )
        elif (
            reference_resources is not None and reference_resources != target_resources
        ):
            # Cross-year: symlink year-independent files from the 2025 reference.
            symlinked = symlink_shared_resources(reference_resources, target_resources)
            if symlinked:
                print(
                    f"  Symlinked {len(symlinked)} year-independent resources from "
                    f"'{reference_resources.name}' → skipped by snakemake."
                )
                files_str = " ".join(str(p) for p in symlinked)
                cleanup_cmd = (
                    f"snakemake --cleanup-metadata {files_str}"
                    f" --configfile {base_config_path} --config {config_override}"
                )
                print("  Cleaning up metadata for symlinked files...")
                os.system(cleanup_cmd)

        # Build and execute the snakemake command.
        snakemake_base = (
            f"snakemake {cores_flag} {SNAKEMAKE_TARGET}"
            f" --configfile {base_config_path} --config {config_override}"
        )

        if dry_run_mode:
            # Dry run first
            dry_run_cmd = snakemake_base + " --dry-run"
            print(f"Dry-run command: {dry_run_cmd}\n")
            os.system(dry_run_cmd)

            # Ask for confirmation before the actual run
            print()
            confirm = input("Proceed with the actual run? [y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                print("  Skipped.")
                continue

        print(f"\nRun command: {snakemake_base}\n")
        os.system(snakemake_base)

        # After the reference scenario completes, make it available as the symlink reference
        # for the remaining scenarios in this batch.
        if (
            reference_resources is None
            and scenario_name == reference_scenario
            and target_resources.exists()
        ):
            reference_resources = target_resources
            print(
                f"  Set '{scenario_name}' as symlink reference for subsequent scenarios."
            )

    print("\n" + "=" * 60)
    print("All selected scenarios have been processed.")


if __name__ == "__main__":
    main()
