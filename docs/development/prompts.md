
# Prompts to fine-tune the system

Student-UI: check, whether results of multiple choice is added to the total points and shwon correctly in the footer.



--- Seeding / Demo

Generated more closer-to-reality demo seed :

Add a Pharmacy demo to the seed_demo:
Use the substances from examples/substance_list.csv

For the Pharmacy demo, use
- per Analysis grading with 3 repetions (-2 points penalty), 10 points for correct first analysis, all 3 correct → 10; one wrong → 8; two wrong → 6.
-min points to pass: 30
use integer numbers, starting from 1 for the labspace ID 

Add the following  Analysis and mulitple choice taks to the course: (Ions still given in non-canonical form, please convert):



| **Task** | **Content** |
| --- | --- |
| Practice Analysis (1 Salt) | Cations: **Na+1, K+1, NH4+1**<br>Anions: **Cl-1, SO4-2, NO3-1** |
| Analysis 1 (2 Salts) | Cations: **Na+1, K+1, NH4+1**<br>Anions: **Cl-1, SO4-2, NO3-1** |
| Analysis 2 (max. 3 Salts) | Cations: **Na+1, K+1, NH4+1, Li+1, Ba+2, Mg+2, Ca+2**<br>Anions: **Cl-1, SO4-2, NO3-1, CO3-2** |
| Analysis 3 (max. 3 Salts) | Cations: **Na+1, K+1, NH4+1, Li+1, Ba+2, Mg+2, Ca+2, Al+3, Zn+2, Fe+2, Fe+3, Mn+2, Mn+4, Mn+6, Mn+7,  Ni+2, Co+2, Co+3, Cu+2, Ag+1, Pb+2, Sn+2**<br>Anions: *- not to be determined -* |
| Analysis 4 (max. 4 Salts) | Cations: *- not to be determined -*<br>Anions: **Cl-1, SO4-2, NO3-1, CO3-2, Acetate, SCN-1, S-2, Br-1, I-1, PO4-3, NO2-1** |
| Analysis 5 (max. 4 Salts) | Full analysis covering the entire scope of material previously treated |
| European Pharmacopoeia Monography Analyses | One identity test, purity test, and monograph test on various salts; results to be stated as <u>complies</u> or <u>does not comply</u> |

For the last Monography analysis, use the new mulitple choice feature:
Card	"EP Monograph — [salt]" (title + description/remarks for the monograph reference)	—
Q1 · Identity test	"Does the salt pass the identity test?"	true / false
Q2 · Purity test	"Is the salt pure?"	true / false (or pure / impure)
Q3 · Monograph test	"Does it meet the monograph requirements?"	complies / does not comply
The oxidation state of a certain metal is not important, so for the analysis select any salt with the listed metal ion.

In the chemistry example, use the repeat analysis workflow (after 2 failed), the student gets a new analysis of the same kind, panelty: 5 points.

Add a medicine example (very simple)
With 3 Analyis (per analysis), 3 trials possible,
and some basic chemistry related mulitple choice, simple questions (acid / bases, Amino acids, redox chemistry)

For biology demonstrate the per ion workflow, no retrials, biology/physiology  relevant, simple mulitple choice questions acid / bases, Amino acids, redox chemistry

The name of the analysis instances should always have the labspace_id as last prefix, e.g. Cations1_1, Anions2_1, ...



--- docs
Update the REAME.md to add the new muliple choice feature and grating configuration capablities.

Improve the sphinx markdown documentation. In stead of a large readme, create chapters with links, explaining the application from users and developers perspective. Include installation (all docker variants, SQLITE / Postgres) and usage. 
Explain in reasonable detail the different analyis , multiple choice and grating options, with comprehensive examples. Also deeply explain the Registration process (for stundents and members) and the different authentification / OAUth options, 
and how they can be configured. 
For Admins create a marmaid graph of how a course can be set up (incl. student registration, analysis, muliple choice and time windows ).
For DevOps explain the options for the docker deployment (also hint on how flamecheck can be place behind a load-balancer / webserver with TLS endpoint).


--- Test Staging docker
Finally test the staging docker (by locally generating the docker image /container and run tests against it) - check also, if LOGO settings / QR code now works.



--- docs

update the version info in the about sections and add the gitlab pages link to the about sections.
