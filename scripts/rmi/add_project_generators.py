# SPDX-FileCopyrightText: Open Energy Transition gGmbH and contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""Add an additional renewable energy project to the brownfield network.

For baseline scenarios (``project.enable: false``), the network is passed
through unchanged.  For project scenarios (``project.enable: true``), the
generators defined in the CSV pointed to by ``project.file`` are inserted
with **fixed** installed capacity (``p_nom = p_nom_min = p_nom_max``,
``p_nom_extendable = False``).

The techno-economic parameters (``marginal_cost``, ``capital_cost``,
``efficiency``) and the hourly capacity factor profile (``p_max_pu``) are
copied from the matching existing generator that was placed in the network by
``add_existing_baseyear``.  The lookup key follows the naming convention used
by that script:

    ``{bus} {resource_class} {carrier}-{baseyear}``

for example ``DE0 0 solar-2025``.

If the exact key is absent (e.g. because IRENASTAT returned zero capacity for
that country/carrier combination), a fallback to the first generator with the
same carrier on the same bus is applied.

CSV columns
-----------
name          : Human-readable label (informational only, not used in the model)
country       : ISO 3166-1 alpha-2 country code (e.g. ``DE``)
carrier       : PyPSA carrier string (e.g. ``solar``, ``onwind``)
p_nom_MW      : Installed capacity of the project in MW
resource_class: (optional, default 0) resource-class bin used for profile lookup

This rule sits between ``add_existing_baseyear`` and
``solve_sector_network_myopic`` in the Snakemake DAG:

    add_existing_baseyear → _brownfield.nc
    add_project_generators → _brownfield_project.nc
    solve_sector_network_myopic (reads _brownfield_project.nc)
"""

import logging

import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)


def add_project_generators(
    n: pypsa.Network,
    project_file: str,
    baseyear: int,
) -> None:
    """Insert project generators defined in *project_file* into *n*.

    Parameters
    ----------
    n:
        Network to modify in-place (brownfield, after add_existing_baseyear).
    project_file:
        Path to the CSV file listing the project generators.
    baseyear:
        Planning horizon year, used to find the matching existing generator
        for profile / cost copying (e.g. 2025).
    """
    project_gens = pd.read_csv(project_file)

    for _, row in project_gens.iterrows():
        country = str(row["country"])
        carrier = str(row["carrier"])
        p_nom_mw = float(row["p_nom_MW"])
        resource_class = str(int(row.get("resource_class", 0)))

        # ------------------------------------------------------------------
        # 1.  Find the AC bus for this country
        # ------------------------------------------------------------------
        ac_buses = n.buses[
            (n.buses.carrier == "AC") & (n.buses.country == country)
        ]
        if ac_buses.empty:
            logger.warning(
                "No AC bus found for country '%s'. Skipping row.", country
            )
            continue
        bus = ac_buses.index[0]
        if len(ac_buses) > 1:
            logger.info(
                "Multiple AC buses found for country '%s'. "
                "Using the first one: '%s'.",
                country,
                bus,
            )

        # ------------------------------------------------------------------
        # 2.  Locate the source generator for profile / cost cloning
        #     Convention from add_existing_baseyear:
        #       "{bus} {resource_class} {carrier}-{baseyear}"
        # ------------------------------------------------------------------
        source_name = f"{bus} {resource_class} {carrier}-{baseyear}"
        if source_name not in n.generators.index:
            candidates = n.generators[
                (n.generators.carrier == carrier) & (n.generators.bus == bus)
            ]
            if candidates.empty:
                logger.warning(
                    "No source generator found for carrier '%s' on bus '%s'. "
                    "Skipping row.",
                    carrier,
                    bus,
                )
                continue
            source_name = candidates.index[0]
            logger.info(
                "Primary source '%s %s %s-%s' not found. "
                "Using fallback source generator: '%s'.",
                bus,
                resource_class,
                carrier,
                baseyear,
                source_name,
            )

        # ------------------------------------------------------------------
        # 3.  Copy techno-economic parameters from the source generator
        # ------------------------------------------------------------------
        marginal_cost = n.generators.at[source_name, "marginal_cost"]
        capital_cost = n.generators.at[source_name, "capital_cost"]
        efficiency = n.generators.at[source_name, "efficiency"]

        # p_max_pu: time series if present in generators_t, else static scalar
        if source_name in n.generators_t.p_max_pu.columns:
            p_max_pu = n.generators_t.p_max_pu[source_name]
        else:
            p_max_pu = n.generators.at[source_name, "p_max_pu"]

        # ------------------------------------------------------------------
        # 4.  Add the project generator
        # ------------------------------------------------------------------
        gen_name = f"{bus} {resource_class} {carrier}-project"
        if gen_name in n.generators.index:
            logger.warning(
                "Generator '%s' already exists in the network. Skipping.", gen_name
            )
            continue

        n.add(
            "Generator",
            gen_name,
            bus=bus,
            carrier=carrier,
            p_nom=p_nom_mw,
            p_nom_min=p_nom_mw,
            p_nom_max=p_nom_mw,
            p_nom_extendable=False,
            marginal_cost=marginal_cost,
            capital_cost=capital_cost,
            efficiency=efficiency,
            p_max_pu=p_max_pu,
        )
        logger.info(
            "Added project generator '%s': %.1f MW %s at bus '%s' "
            "(copied profile/costs from '%s').",
            gen_name,
            p_nom_mw,
            carrier,
            bus,
            source_name,
        )


if __name__ == "__main__":
    if "snakemake" not in dir():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("add_project_generators")

    set_scenario_config(snakemake)
    configure_logging(snakemake)

    project_config = snakemake.params.project
    baseyear = snakemake.params.baseyear

    n = pypsa.Network(snakemake.input.network)

    add_project_generators(
        n=n,
        project_file=project_config["file"],
        baseyear=baseyear,
    )

    n.export_to_netcdf(snakemake.output[0])
