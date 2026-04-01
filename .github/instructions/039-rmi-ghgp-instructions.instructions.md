# Introduction
This instruction file provides context and guidelines for the **GHGP project** between Open Energy Transition (OET), the consultancy company where I work as Energy System Modeller, and Rocky Mountain Institute (RMI), which is the client.

These names and links will be used in this file, and the project will be referred to as _the project_ or _the GHGP project_ throughout the document:
- [Open Energy Transition (OET)](https://www.openenergytransition.org/).
- [Rocky Mountain Institute (RMI)](https://rmi.org/).
- [Greenhouse Gas Protocol (GHGP)](https://ghgprotocol.org/).
- [Scope 2 Guidance](https://ghgprotocol.org/sites/default/files/2023-03/Scope%202%20Guidance.pdf)
- [Guidelines for Quantifying GHG Reductions from Grid-Connected Electricity Projects](https://ghgprotocol.org/sites/default/files/2022-12/.Guidelines%20for%20Grid-Connected%20Electricity%20Projects.pdf).
- [PyPSA-Eur](https://pypsa-eur.readthedocs.io/en/latest/).
- [PyPSA](https://pypsa.org/).
- [ENTSO-E](https://www.entsoe.eu/).
- All the relative paths listed in this file are relative to the root of this file. For instance, the path to the README file is ../../README.md, which means that the README file is located two levels up from the current file.

# Project description
The goal of the project is to calculate a retrospective consequential performance metric in the context of the GHGP for the European power system. The project will involve using the PyPSA-Eur model, with a backcasting approach of the historical period 2020-2025. However, no additional validation against actual historical dispatch is needed.

The project has a duration of around 2 months (April-May 2026) and the public GitHub repository is [pypsa-eur-ghgp](https://github.com/open-energy-transition/pypsa-eur-ghgp).

## Project Context
The GHGP convened a subworking group on consequential assessment for electricity sector emissions focusing on the following additional activities in the Scope 2 Guidance framework:
- Clarify the relationship between scope 2 inventory accounting and electricity sector project accounting methodologies such as in the Guidelines for Quantifying GHG Reductions from Grid-Connected Electricity Projects.
- Explore whether alternative or additional scope 2-related metrics should be included in a GHG emissions report.

In order to apply consequential accounting to a GHG emissions report, it is recommended that consequential accounting is adapted into a retrospective consequential performance metric that should provide a standardized, practicable, and scientifically validated approach to generate a useful retrospective approximation of a company’s comprehensive consequential impact.

More information about the project context can be found in this [Notebook LM](https://notebooklm.google.com/notebook/a3d21fcd-f00f-41b6-a952-044082dae1e1).

## Appendix on consequential performance metric
**Note:** This section is work in progress and will be updated as we further develop the project.

When it comes to the study and the specific questions RMI has:
- We are trying to run a comparison between capacity expansion modelling and a consequential performance metric that either: uses a fixed omega (e.g., 50%), OR calculates an hourly omega based on the equations laid out in Uday and I’s earlier paper. Omega is used to define the share or build margin (BM) and operating margin (OR): ER_baseline = omega * BM + ( 1 - omega ) * OM (see Guidelines for Quantifying GHG Reductions from Grid-Connected Electricity Projects).
- We believe the best approach to this is to model a “backcast” capacity expansion model to develop a counterfactual for a typical renewable energy project in a typical geography in Europe. Our goal is to pick a relatively common and well understood type of intervention in a fairly typical market/geography. We welcome OETs recommendations on the ideal geography/project type based on data availability, but were thinking something along the lines of:
  - A sizable – but not hyperscalor sized – solar PPA (~10 MW?) in Germany, looking at project initiation in 2017 and modelled with counterfactual through 2025.
- We would then compare the modelled avoided emissions from the counterfactual described above to the calculated consequential impact using historic hourly operating and build margin data:
  - We are in touch with Watttime about a potential calculation tool that could support this, but are also curious what historical data OET might already have access to.
  - If calculating the hourly omega would be cost prohibitive, RMI would consider running this portion ourselves.
- It would be our intention to seek publishing this work jointly in some way, potentially seeking
publishing in a journal. We also welcome your thoughts on the merit of this approach.

# PyPSA-Eur model
This project uses a PyPSA-Eur model with these features:
- Geographical scope: all ENTSO-E countries, with at least 1 node per country, and more nodes if needed.
- Temporal scope:
  - Single year optimization, with backcasting years to be analyzed: 2020, 2021, 2022, 2023, 2024, and 2025. Consider that only 2020 and 2025 are typical planning horizons used in PyPSA-Eur.
  - Hourly resolution. 
- Sectoral scope: electricity sector.
- Type of optimization: no capacity expansion, only dispatch optimization.
- For each year, two scenarios are modelled:
  - Baseline: actual historical evolution.
  - Project: counterfactual with an additional renewable energy project in a specific country. Different technologies, sizes, and locations has to be tested, so that there might be more than one Project scenario (e.g., Project 1 with solar in Germany, Project 2 with solar in Poland, etc..).

The model implementation is made of two phases:
1. Test model: a small model with reduced geographical and temporal scopes is implemented to test the configuration and the workflow.
2. Final model: the full model with the complete geographical and temporal scopes is implemented to run the final analysis.

## 1-Test model
**Note:** This section is work in progress and will be updated as we further develop the project.

This phase is made of the following steps:
1. Define the test model base configuration:
  - Geographical scope: one country, with at least 1 node.
  - Temporal scope: one month, with a time resolution of 3 hours.
  - Sectoral scope: only electricity sector, with a realistic set of technologies available for the period 2020-2025 (i.e., no direct air capture, no synthetic fuels, etc...).
  - No extendable carriers, no transmission expansions, load shedding allowed.

2. Implement a strategy to filter only the power plants, transmission lines, and load corresponding to a specific backcasting year. For instance, for the backcasting year 2024, only the power plants and transmission lines that are active in 2024 and the 2024 load should be included in the model. In this regard, relevant configuration settings are in the _electricity_ section (https://pypsa-eur.readthedocs.io/en/latest/configuration.html#electricity) and in the _load_ section (https://pypsa-eur.readthedocs.io/en/latest/configuration.html#load):
  - powerplants_filter
  - transmission_limit
  - fixed_year
  - There might be other relevant configuration settings that we are not aware of yet, so we need to further investigate this aspect.
  
3. Finalize the strategy to run a dispatch-only optimization, without capacity expansion. This means that the model should not be able to build new power plants or transmission lines, but only to dispatch the existing ones. In this regard, relevant configuration settings are in the _electricity_ section (https://pypsa-eur.readthedocs.io/en/latest/configuration.html#electricity) and in the _solving_ section (https://pypsa-eur.readthedocs.io/en/latest/configuration.html#solving):
  - extendable_carriers
  - transmission_limit
  - options.load_shedding
  - There might be other relevant configuration settings that we are not aware of yet, so we need to further investigate this aspect.

4. Finalize the most suitable sectoral scope and the most realistic set of technologies available for the period 2020-2025. In this regard, relevant configuration settings are in the _sector_ section (https://pypsa-eur.readthedocs.io/en/latest/configuration.html#sector) and in the _adjustments_ section (https://pypsa-eur.readthedocs.io/en/latest/configuration.html#adjustments):
  - There might be other relevant configuration settings that we are not aware of yet, so we need to further investigate this aspect.

5. Define the project scenario with the additional renewable energy project.

6. Implement an automatic workflow to run the baseline and project scenarios for all the selected backcasting years. A test workflow might involve running only 3 backcasting years.

## 2-Final model
**Note:** This section is work in progress and will be updated as we further develop the project.

The final model will involve all the countries considered in the geographical scope and several project scenarios.

## Appendix on PyPSA-Eur model
**Note:** This section is work in progress and will be updated as we further develop the project.

Besides the links provided at the beginning of the documents for PyPSA-EUR and PyPSA, here are some additional resources that can be useful for the project:
- High level overview of PyPSA-Eur and the repository structure is available in ../../README.md
- PyPSA-Eur workflow is based on [snakemake](https://snakemake.readthedocs.io/en/stable/). The workflow is defined in ../../Snakefile.
  - The snakemake rules are in the folder ../../rules, while the scripts used by the snakemake rules are definied in the folder ../../scripts
- [Pixi](https://pixi.prefix.dev/latest/) is used for package management.
- The configurations are defined in the folder ../../config.