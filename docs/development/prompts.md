
# Prompts to fine-tune the system

--- Improved ion representation
use the following convention for the ions: 
charge = substring from the last '+'/'-' to end; formula = everything before it. 
Examples: S2O8-2, PO4-2, Na+1

Explain it in the help system, documantation. Change this in all documentation, help, specs, implementation

Use this information to improve the submission (and confirmation windows/pages)


--- multiple choice

Add a new per-course mulitple choice feature:

mulitple questions per card (max. 3 questions / card)
time windowed

Admin definable questions and grading, per course 

grading: default 10 points per card if all correct, 2 points panelty for each wrong answer. points and panelty shall be per course configurable


--- Seeding / Demo

Generated more closer-to-reality demo seed :

Seed/demo analyis: Move Pharmacy example to Geology 

Use the substances from examples/substance_list.csv

For the Pharmacy use
Per Analysis grading with 3 repetions (-2 points panelty), 10 points for correct first analysis, min points to pass: 30

| **Task** | **Content** |
| --- | --- |
| Practice Analysis (1 Salt) | Cations: **Na+, K+, NH4+**<br>Anions: **Cl-, SO4 2-, NO3-** |
| Analysis 1 (2 Salts) | Cations: **Na+, K+, NH4+**<br>Anions: **Cl-, SO4 2-, NO3-** |
| Analysis 2 (max. 3 Salts) | Cations: **Na+, K+, NH4+, Li+, Ba 2+, Mg 2+, Ca 2+**<br>Anions: **Cl-, SO4 2-, NO3-, CO3 2-** |
| Analysis 3 (max. 3 Salts) | Cations: **Na+, K+, NH4+, Li+, Ba 2+, Mg 2+, Ca 2+, Al 3+, Zn 2+, Fe 2+/3+, Mn 2+/4+/6+/7+, Ni 2+, Co 2+/3+, Cu 2+, Ag+, Pb 2+, Sn 2+**<br>Anions: *- not to be determined -* |
| Analysis 4 (max. 4 Salts) | Cations: *- not to be determined -*<br>Anions: **Cl-, SO4 2-, NO3-, CO3 2-, Acetate, SCN-, S 2-, Br-, I-, PO4 3-, NO2-** |
| Analysis 5 (max. 4 Salts) | Full analysis covering the entire scope of material previously treated |
| European Pharmacopoeia Monography Analyses | One identity test, purity test, and monograph test on various salts; results to be stated as <u>complies</u> or <u>does not comply</u> |

For the last Monography analysis, use the new mulitple choice feature.

In the chemistry example, use the repeat analysis workflow (after 2 failed), the student gets a new analysis of the same kind, panelty: 5 points.

Add a medicine example (very simple)
With 3 Analyis (per analysis), 3 trials possible,
and some basic chemistry related mulitple choice, simple questions (acid / bases, Amino acids, redox chemistry)

For biology demonstrate the per ion workflow, no retrials, biology/physiology  relevant, simple mulitple choice questions acid / bases, Amino acids, redox chemistry

The name of the analysis instances should always have the labspace_id as last prefix, e.g. Cations1_1, Anions2_1, ...


---- e-mail notification

Admin->couses:
Configure possiblity to send an e-mail on each submission to the student (and on configuration in the Admin->settings->notifications) to the assistent.

The e-mail should be PGP encrypted/signed
pgp encryption should be configurable in the Admin->settings->notification page

As an additional safety layer, sending emails **must** be enabled by an environment variable for the docker container: ALLOW_EMAILS (if not enabled e-mails will not be send, even if configured in admin->settings->notifications). 
This shall prevent misuse in staging/demo environments.





