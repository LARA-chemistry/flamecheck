# Changelog

## v0.1.0 (2026-10-05)

### Features

- Show student login name and labspace id in the detail modal ([`1381993`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/13819934674e451f9f21fd65a66440956a3eb67c))
- Rebuild the demo seed around a geology showcase ([`c93c921`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/c93c9211e459ed1243002eb818e9d297ebb2c9b5))
- Per-course editor tab in courses + shared designer ([`f169cdc`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/f169cdc23d573429af1e265acc94d8c17332ad1e))
- Seed a european pharmacopoeia monograph example ([`844a254`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/844a254b90b7cdc54c25dae6684784a19d5e97b5))
- Add per-course multiple-choice cards ([`caa4c99`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/caa4c994497a1cb0db3e14949c9bdd8c82039ffa))
- Row-click edit mode for substances and analysis types ([`c5728a4`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/c5728a464833bb4ddd928c01eeace752b725f0e9))
- Adopt canonical ion symbol convention with iupac rendering ([`bdd23d3`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/bdd23d3189d2615a0e0ebcef74c53548e34c6aea))
- Pubchem/wikipedia helper scripts added ([`46fec89`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/46fec89d1b672356fa970d300c2338fbbcb26ce9))
- Improved, real substance list added to examples ([`173af3e`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/173af3e195507a68094e7c1f90630fc1cd6325ab))
- Add keycloak (openid connect) sso support ([`d5227ba`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/d5227ba2da26934de836fb5375f903c52ddb495e))
- Show exact submission time in the student detail view ([`5d31c88`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/5d31c8841064f25ed4e02ec574fb2c9424688d63))
- Add "export to csv" for the substance catalog ([`b6b809f`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/b6b809f491f97b93848cb4039a87efca84f5c8f2))
- Return to the card view after every analysis submission ([`618cbda`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/618cbdaeac4297a6d19eb84f3db0ca8b8054c030))
- Edit rows on click + add analysis-instance editor ([`a38112b`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/a38112b3091b9fe8158bd3ce851b63f89157c42e))
- Add "new analysis" submission mode with re-trials ([`812eb8f`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/812eb8ffc7159fca6e191601196cb66b6a357efe))
- Manual / self-registration / oauth onboarding modes ([`ba026f2`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/ba026f23ef6825241264fff2a8cdba00097f5491))
- Course members (students + assistants) management ([`b3d5597`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/b3d5597bad2fe6b64a962619ea4d33bfb133042b))
- Course detail view with tabbed navigation ([`28ee85f`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/28ee85ff45b934e0b1606db93c97d8cc84fdd321))
- Resubmit until limit, results behind explicit button ([`8a11372`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/8a1137229fe2de40d4d40fa96ae656b37fac0a5a))
- Logos added ([`21ff003`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/21ff0033a37c3c75c872c4bb9778bdb9ea4605dd))
- Student management (edit, add/delete, csv import) ([`e97dfd3`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/e97dfd32363f7de4003452870f4c126537616d63))
- Greyed-out cards only open when a result exists ([`481c3f4`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/481c3f4bbfb1616a94fa49339b49ce996211628d))
- Center login qr below the card; allow png logo ([`96426c0`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/96426c0c9ea38e77b5a041405db02f6bce61536b))
- Link pubchem ids and wikipedia references ([`4e332e0`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/4e332e0c02a61245f9347792b5bb572c777d76ff))
- Login-page branding (university logo + login qr) ([`778ed38`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/778ed38801471406d22fa7022a5e2b3595a3a542))
- Profile modal with core data and analysis results ([`529cb25`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/529cb2520e9d623f5af278d39b918d0628b078ba))
- Add telephone field to the user model ([`4e7ccfb`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/4e7ccfb98dbe8b20ca96e0a3e6972461b3107da0))
- Show labspace id and make inactive cards clickable ([`0afcd8c`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/0afcd8c27133ab46824019735b657bdde73fc258))

### Bug fixes

- Proactively refresh the access token before expiry ([`7b1aaf7`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/7b1aaf7a0957e625b9a1266a71e504e951101b5c))
- Migrate a fresh database before seeding ([`1309a45`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/1309a45fa117a4085cf6d9023bbbe3be9643e9f8))
- Serve branding media in production and cache-bust preview urls ([`74b07e4`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/74b07e40903bc6d20d0c5919887c1c72ace9989d))
- Always show results once the submission limit is reached ([`87e185d`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/87e185d633e85382e7e356bd5ee75e070d28e7bc))
- Track django migrations so ci and docker images can build the schema ([`bad9920`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/bad9920f66d618476cff9a3c887166b32f3ec6c3))
- Versioning in pyproject.toml and .gitlab-ci.yml; ([`341e2c0`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/341e2c0eb78c51f86d48f452b8744fd342e302f1))
- Make check_migrations tests robust across sqlite builds ([`1fc039d`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/1fc039d909799d06172df74289f18e5ca8293766))
- Self-heal a corrupt migration state on container start ([`f2a2c6e`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/f2a2c6e9ab02bc276446affca53f6e5e5f0a8c69))

### Documentation

- Document the authentication setup and all sign-in methods ([`259c15a`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/259c15a87512954de2ae98bc1a17b771e00f6daf))

## v0.0.4 (2026-10-02)

### Bug fixes

- .gitlab-ci.yml; faker dependencies added ([`7683082`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/7683082d3d7a44db04ea690c68eddb4782166b13))

## v0.0.3 (2026-10-02)

### Bug fixes

- Docker-compose-staging.yaml - gitlab image added ([`70e19f5`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/70e19f561c2e058e14746badc5edf22f9d2fbf4e))
- Pin node 22.23.3 so npm 11's engine requirement is satisfied ([`4688dcc`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/4688dcce99ee830fa980f6a5565d07374da7b09a))

## v0.0.2 (2026-10-02)

### Bug fixes

- Align npm version so the vite/rolldown native binding installs ([`0e03914`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/0e039141acb99333a4c9754dcde0fe8997c647b4))

## v0.0.1 (2026-10-02)

### Features

- Add about section to the help panels ([`77fa4bd`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/77fa4bd618a8614056b1d4389484c437fedcc31b))
- Pin the footer to the viewport bottom on large screens ([`63d088e`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/63d088efcfd99b9b9b3550fb5d89a31983ad0170))
- Move points summary below the progress bar in the footer ([`c35fd9f`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/c35fd9fa4bb6d3c9ed80e35f4b641326e4d45351))
- Add students/substance view toggle above the course table ([`0d89547`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/0d8954733201b59058eec6ed98a8e2820180163d))
- Substances csv template uses ';' columns and ',' ion lists ([`cfcfdd1`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/cfcfdd180e7fbba13f4e17ce2eb06791c5904a2f))
- Csv import of analysis composition (salts → answer key) ([`5e1a01e`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/5e1a01eaf0fd8789eff31830e3d87044d56a4fcc))
- Database backup/restore with scheduled in-process timer ([`108123f`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/108123ff66940a812756bceccdfcccbb8bac7e8d))
- Csv import of course analyses with labspace-id assignment ([`4bf319a`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/4bf319a1a39c54cec55cdf2ecb3ae97a3b7c9d49))
- Course progress dock with red-yellow-green bar ([`b9618fd`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/b9618fd4a4d71914871968e1c88a51b46b49ac20))
- Per-course pass line and per-ion/per-analysis mode ([`2259a2d`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/2259a2d4e370b88a6b5798f500e5646210eb3de3))
- Add a month view to the course window calendar ([`a1d55f7`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/a1d55f7899eb4558ac02242d7b905f333ed07063))
- Upgrade the course window calendar to a week view ([`ab40b3b`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/ab40b3bb96003ce6a89ffe976737af6f1393741a))
- Compact the student header on mobile phones ([`69f80b8`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/69f80b8e2927dcceec8054637431dcc0f3ab2238))
- Add a per-course window calendar to visualise analysis windows ([`a68a7ad`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/a68a7ada6903ed27e1e37c39f34cb1642d377abc))
- Set the analysis window per analysis from the analysis types page ([`a0b09a1`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/a0b09a18555fcebdeff2175aa6f2faccc5a8476d))
- Use an ordered grid to align ions on the submission page ([`89d2dc6`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/89d2dc6855837f963439854c8ce47fc48af4276c))
- Move the course name to the top of the page ([`0250851`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/0250851c7bfe523a108de910252ffdef15387a56))
- Seed the demo dataset on staging boot ([`f16e564`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/f16e56499bfda5bc8faf634a50a583f44908c603))
- Align + split ions by kind in the submission breakdown ([`65c5681`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/65c5681dd873d111724be14fb3585a84d3cd6879))
- Courses as default view, right-aligned settings with icon, drop assignments nav ([`46a579e`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/46a579e6dec6edb8c852ad815ac9155b7a9a5406))
- Per-student progress bar in the course roster ([`0d3bc3b`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/0d3bc3b6d1ef181cc549523f4d59cbae0152c050))
- Add a chemistry course as the default demo course ([`74d6bdc`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/74d6bdce7978415356b53062129e2302281ad837))
- Course header, matriculation no, window intervals, submission history ([`7b13d87`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/7b13d87829d6bd605460f316c4a6756b97716929))
- Add seed_demo command for factory-based staging data ([`61c8504`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/61c850481589dce936aaaaef8cb6a051364d5712))
- Add password show/hide eye toggle ([`b248f49`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/b248f4986488fd18d5acaf09199a7baed234c928))
- Assign students and manage analyses from each course ([`af1e333`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/af1e333db56199d92be63b5feb97077f06837b42))
- Grade each course with its own settings ([`b7fbb35`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/b7fbb35fc3f11459a48e80ac8343540c2f507f01))
- Improve analysis cards and results view ux ([`f0027c9`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/f0027c9bd823390d14be4b15ba0fea91ec1df5e2))
- Add resizable/closable help panel on large screens ([`829d4fc`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/829d4fca0a8171448a515085825a8883bb4c6f88))
- Randomly assign substances to students per analysis ([`4a0af74`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/4a0af74b20f101db4b2fd9f6c151cb623db38f8b))
- Add csv upload for substances ([`a2046f3`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/a2046f307b0ed2b5df248cc3e067987e3bdaf918))
- Add example datasets and demo verification script ([`12ff12c`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/12ff12cf4de6b8ae254a1f11ca627067bfcb753e))
- Add per-concern admin pages and per-student statistics ([`4de1908`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/4de190843e6552a23518bc7e85cce4ffe9e3cf90))
- Improved ui/ux - round 2 ([`ebda8f6`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/ebda8f60c420abc7df431d1666312febdee50cae))
- Improved ui/ux - round 1 ([`91493b4`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/91493b428522114c5b7dbb97696f6c44a4e1bde4))
- Simple routing working ([`c20019e`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/c20019e4bc505a7a8d0e84db251ce4b70b87d588))
- Factory-boy support for all models ([`dc3024c`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/dc3024c961733f01ac8ccef3a0a3978b6c5a4b07))
- Architecture documentation added ([`bdb3b3a`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/bdb3b3af30a135a6dafbec33816de71c8d4ddb84))
- 1st dsh iteration ([`ac157f0`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/ac157f005d81d49843ae6a57d2e42f1835c8117b))
- First draft of software specification ([`db63e64`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/db63e6489db50aab38d8bef13f53d7a56fa9e4a9))

### Bug fixes

- Make the window end time render unambiguously ([`e4ad3db`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/e4ad3dbd8faee0f65d241b7a7a318c42f57111ed))
- Stop substance view duplicating on view toggle ([`ca84877`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/ca84877f7006191c18d82256b14c44c500f8bbb4))
- Move student progress bar to page footer ([`fb5824f`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/fb5824f3afdab0a1e793a613a01b9cf6ef7fc39e))
- Ci/cd tests now with node ([`e6a46e4`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/e6a46e48198746b1530cb9cddb0c2e50b7615cb4))
- Tests disabled in ci/cd ([`5e9c460`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/5e9c460e48c5872319539e195e834c24f8b87be5))
- Tests disabled in ci/cd ([`4104ce6`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/4104ce602e8ec71bf7f444ad92264d48d855cef6))
- Tests disabled in ci/cd ([`ad21018`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/ad2101873b992cbf6d93c0fe227a77e8ee88f50b))
- Readme.md improved ([`aabcbd6`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/aabcbd67851919612c680452939611807f4c9137))
- First draft of factory boy support ([`3eb412a`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/3eb412a8c0b24b6d86dd21920f30a957f606f28d))
- Sqlite as default database ([`787b291`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/787b29131bc59a51d20495bdca50578a3f815462))
- Readme.md improved ([`3062245`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/3062245370a03c540a3a049b81a6d7b62efaf98d))
- Software specification ([`948df72`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/948df725f38902a03178e7c5b03dabcdbef3ddb8))
- Pyproject.toml ([`6b207b2`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/6b207b25bc9769cbce4923f058a7ee7adb813e2e))
- Django app structure - uv workspace ([`b1f339f`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/b1f339fcf9841cc745de390505ca2cb6b86b37f7))
- Software specification ([`cf6bba9`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/cf6bba962ecb7e058b234556faf9f47eb0872f03))

### Build system

- Update python and js dependencies to latest stable ([`dc6fea8`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/dc6fea85d7c4ed3d2fc6ec7489c0cff335a6e2dd))

### Documentation

- Sync readme with compose files, demo seeding and test suite ([`55bd055`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/55bd0558d827d5f9963ef0b7d1818a96fc733920))
- Document db backend + init_admin superuser credentials in .env-template ([`cdcadf9`](https://gitlab.com/opensourcelab/cheminformatics/flamecheck/-/commit/cdcadf946288ba960fe11ddfb73b60a0b19d3e56))
