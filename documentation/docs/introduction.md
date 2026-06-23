# Introduction

The goal of this project is to calculate, by means of PyPSA-Eur, a retrospective consequential performance metric in the context of the [Greenhouse Gas Protocol (GHGP)](https://ghgprotocol.org/). The retrospective approach implied to use PyPSA-Eur to simulate past years, but no additional validation against actual historical dispatch has been required.

>[!NOTE]
> Currently, the project repository allows the user to generate traditional PyPSA-Eur results, whereas the calculation of the actual performance metric will be added in a later stage.

---

## Project context

This project lies within the broader discussion within the GHGP framework about the use of consequential performance metrics in GHG indirect emission report of companies. In this regard, the GHGP convened a subworking group aiming to:

- Clarify the relationship between [**scope 2 inventory accounting**](https://ghgprotocol.org/sites/default/files/2023-03/Scope%202%20Guidance.pdf) and [**grid-connected project accounting**](https://ghgprotocol.org/sites/default/files/2022-12/Guidelines%20for%20Grid-Connected%20Electricity%20Projects.pdf) methodologies, where:

    - Scope 2 inventory is an attributional method accounting for indirect emissions from purchased electricity.
    - Grid-connected project accounting is consequential, seeking to quantify the system-wide change caused by a specific action (i.e., procure electricity from a newly built project).
  
- Explore whether alternative or additional scope 2-related metrics should be included in a GHG emission report.

The application of a **consequential** accounting method requires a counterfactual representation of what would have happened without the project. Also, it is recommended that such a method is applied with a **retrospective** approach (i.e., looking backword at the historical period), to provide a standardized, practicable, and scientifically validated approach to generate a useful approximation of a company consequential impact.

---

## Project assumptions

The need for a retrospective metric implied to develop a model capable to simulate the historical period, i.e., a **dispatch-only** model. In particular, the historical period involved yearly simulations **from 2020 to 2025**. Then, to balance spatial and temporal resolution with computational efficiency, the model scope is defined as follows:

* Spatial Scope:
    * Geography: 34 countries (as the [default PyPSA-Eur configuration](https://pypsa-eur.readthedocs.io/en/latest/configuration.html#countries)).
    * Resolution: 39 nodes (ensuring that each country is represented by at least one node).
* Temporal resolution: 3-hours interval.
* Sectoral Scope: the model is limited to the electricity sector.

---

## Installation

Clone the repository:

```sh
git clone https://github.com/open-energy-transition/pypsa-eur-ghgp
```

You need [pixi](https://pixi.sh/latest/) to run the analysis.
Once installed, activate your pixi environment in a terminal session:

```sh
pixi shell
```

>[!NOTE]
>`pixi` will create a distinct environment in every project directory, even if you have identical copies of a project cloned locally.
>As there is a common system-level package cache, `pixi` efficiently conserves disk space in such cases.

>[!TIP]
>If `pixi` isn't working, you can install from one of the fallback `conda` environment files found in `envs`.
>For more details see [the PyPSA-Eur installation guide](https://pypsa-eur.readthedocs.io/en/latest/installation.html).

---

## Run scenarios

The script [`run/backcasting_run.py`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/run/backcasting_run.py) has been developed to interactively and automatically run the scenarios available in [`config/scenarios.rmi.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/scenarios.rmi.yaml). The script is useful as it identifies the many resources that are common across the scenarios, reducing the number of rules included in the snakemake workflows.

The interactive steps are listed below, whereas for more details on model configurations and the script see, respectively, sections [Configuration](configuration.md) and [Scenarios](features/scenarios.md).

### How it works
After activating the project environment (i.e., `pixi shell` if using the default environment), navigate to the root directory of the project, open the terminal, and execute the script:
```bash
python run/backcasting_run.py
```

The script guides the user through a series of interactive prompts to configure the run(s):

1. **Select configuration:** chose one from the available configurations (e.g., full or test model). Each configuration is made of a base configuration file (e.g., [`config/config.rmi.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/config.rmi.yaml)), containing all the common settings across the available scenarios, and a scenario configuration (e.g., [`config/scenarios.rmi.yaml`](https://github.com/open-energy-transition/pypsa-eur-ghgp/blob/dfde908a1485162deff1ecd07be223eafa479cd2/config/scenarios.rmi.yaml)), containing the specific scenario settings.
2. **Select scenario(s):** chose the scenario(s) to run from the available ones, including the possibility to run them all.
3. **Select the number of CPUs:** chose how many cores to use.
4. **Select dry-run:** chose whether to dry-run or not before each scenario. The dry-run allows the user to first look at the rules to be run without actually run the snakemake workflow.