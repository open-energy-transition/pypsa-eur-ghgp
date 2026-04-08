# SPDX-FileCopyrightText: Open Energy Transition gGmbH and contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Interactive runner for GHGP backcasting scenarios.

Usage (from the repo root):
    python run/backcasting_run.py

The script reads available scenarios from config/test/scenarios.rmi.yaml,
lets the user select one or more scenarios (by year or name), generates a
temporary merged config, and runs `snakemake solve_sector_networks` for each.

Resource sharing
----------------
`data/` is always shared (static datasets, never written by snakemake).
`resources/` uses `policy: false` — each scenario has its own subfolder
`resources/{scenario_name}/`. Using `policy: "base"` is not possible in
myopic mode (path mismatch between producer and consumer of costs_processed.csv).

However, many resource files do NOT depend on the backcasting year and are
identical across all scenarios. To avoid redundant computation, before running
scenario N>1 this script creates **symlinks** in `resources/{scenario_N}/`
pointing to the already-computed files of the first completed reference scenario.
Snakemake sees the symlinked outputs as already produced and skips those rules.

Year-independent files (safely symlinked):
  - profile_{clusters}_{tech}.nc         renewable capacity factors (cutout-based)
  - availability_matrix_{clusters}_{tech}.nc  exclusion zones (geographic)
  - regions_*.geojson / *_shapes.geojson geographic shapes
  - networks/base*.nc                    OSM network before adding electricity
  - busmap, linemap, pop_layout, temp profiles, heat profiles, etc.

Year-dependent files (always recomputed, never symlinked):
  - electricity_demand.csv / electricity_demand_base_s.nc  → load.fixed_year
  - powerplants_s_{clusters}.csv                           → powerplants_filter
  - costs_{year}_processed.csv                             → year in filename
  - networks/base_s_{clusters}_elec*.nc                    → depends on above
  - any file matching _20XX in its name                    → year in filename
"""

import os
import re
from pathlib import Path

import yaml

BASE_CONFIG = "config/test/config.rmi.yaml"
SCENARIOS_FILE = "config/test/scenarios.rmi.yaml"
TEMP_CONFIG = "run/config.rmi_temp.yaml"
SNAKEMAKE_TARGET = "solve_sector_networks"

# Matches _20XX (year 20xx) as a name segment: _2025. / _2025_ / _2025 at end
_YEAR_RE = re.compile(r"_20\d{2}([._]|$)")


# ---------------------- Resource sharing helpers ----------------------


def _is_year_dependent(rel_posix: str) -> bool:
    """Return True if this resource file varies across backcasting years."""
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
    # elec networks depend on powerplants + costs
    if rel_posix.startswith("networks/") and "_elec" in name:
        return True
    return False


def _find_reference_resources() -> Path | None:
    """Return the first existing scenario resources folder, if any."""
    resources = Path("resources")
    if not resources.exists():
        return None
    for d in sorted(resources.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            return d
    return None


def symlink_shared_resources(reference_dir: Path, target_dir: Path) -> list[Path]:
    """Symlink year-independent files from reference_dir into target_dir.

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


def deep_update(original, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(original.get(key), dict):
            deep_update(original[key], value)
        else:
            original[key] = value


def select_scenarios(scenario_list):
    """Let the user select one or more scenarios from the list.

    Enter 0 or 'all' to select all available scenarios.
    Enter a single number/name or a comma-separated list otherwise.
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
    """Ask how many local CPUs to use."""
    while True:
        cpu = input("\nHow many CPUs to use (all or a number)? ").strip().lower()
        if not cpu:
            return None
        if cpu == "all":
            return "-call"
        if cpu.isdigit() and int(cpu) > 0:
            return f"-c{cpu}"
        print(f"  '{cpu}' is not valid. Please enter 'all' or a positive number.")


# ---------------------- Main Script ----------------------


def main():
    # Load available scenarios
    with open(SCENARIOS_FILE) as f:
        scenarios_config = yaml.safe_load(f)

    scenario_list = list(scenarios_config.keys())

    print("=" * 60)
    print("GHGP Backcasting Run Script")
    print("=" * 60)

    selected_scenarios = select_scenarios(scenario_list)
    if not selected_scenarios:
        print("\nOperation cancelled by user.")
        return

    cores_flag = select_cpus()
    if not cores_flag:
        print("\nOperation cancelled by user.")
        return

    print(f"\nCores flag: {cores_flag}")
    print("=" * 60)

    # Track the first completed scenario folder to use as symlink reference
    reference_resources: Path | None = _find_reference_resources()

    # Run each selected scenario
    for scenario_name in selected_scenarios:
        print(f"\nRunning scenario: {scenario_name}")
        print("-" * 60)

        target_resources = Path(f"resources/{scenario_name}")

        # Load base config and merge scenario overrides
        with open(BASE_CONFIG) as f:
            config = yaml.safe_load(f)
        deep_update(config, scenarios_config[scenario_name])

        # Override run settings: direct name, disable scenario file
        # shared_resources.policy stays false (see module docstring for reasoning)
        deep_update(config, {
            "run": {
                "name": scenario_name,
                "scenarios": {"enable": False},
                "shared_resources": {
                    "policy": False,
                    "exclude": [],
                },
            }
        })

        # Write temporary merged config (needed before symlinks + cleanup-metadata)
        with open(TEMP_CONFIG, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)

        # Symlink year-independent files from the reference scenario.
        # Then run --cleanup-metadata so Snakemake does not flag the freshly
        # created symlinks as "incomplete" (files with no completion metadata).
        if reference_resources is not None and reference_resources != target_resources:
            symlinked = symlink_shared_resources(reference_resources, target_resources)
            if symlinked:
                print(
                    f"  Symlinked {len(symlinked)} year-independent resources from "
                    f"'{reference_resources.name}' → skipped by snakemake."
                )
                files_str = " ".join(str(p) for p in symlinked)
                cleanup_cmd = (
                    f"snakemake --cleanup-metadata {files_str}"
                    f" --configfile {TEMP_CONFIG}"
                )
                print(f"  Cleaning up metadata for symlinked files...")
                os.system(cleanup_cmd)

        # Build and execute snakemake command
        snakemake_base = (
            f"snakemake {cores_flag} {SNAKEMAKE_TARGET}"
            f" --configfile {TEMP_CONFIG}"
        )

        # Dry run first
        dry_run_cmd = snakemake_base + " --dry-run"
        print(f"Dry-run command: {dry_run_cmd}\n")
        os.system(dry_run_cmd)

        # Ask for confirmation before the actual run
        print()
        confirm = input("Proceed with the actual run? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("  Skipped.")
            if os.path.exists(TEMP_CONFIG):
                os.remove(TEMP_CONFIG)
            continue

        print(f"\nRun command: {snakemake_base}\n")
        os.system(snakemake_base)

        # Clean up temp config
        if os.path.exists(TEMP_CONFIG):
            os.remove(TEMP_CONFIG)
            print(f"\nCleaned up: {TEMP_CONFIG}")

        # After the first run completes, use this scenario as the symlink reference
        # for all subsequent scenarios in this batch
        if reference_resources is None and target_resources.exists():
            reference_resources = target_resources
            print(f"  Set '{scenario_name}' as symlink reference for subsequent scenarios.")

    print("\n" + "=" * 60)
    print("All selected scenarios have been processed.")


if __name__ == "__main__":
    main()
