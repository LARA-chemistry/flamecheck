# Contributing

Contributions are welcome, and they are greatly appreciated! Every little helps, and credit will always be given.

You can contribute in many ways:

## Types of Contributions




### Report Bugs

Report bugs to [our issue page][gl-issues]. If you are reporting a bug, please include:

- Your operating system name and version.
- Any details about your local setup that might be helpful in troubleshooting.
- Detailed steps to reproduce the bug.

### Fix Bugs

Look through the GitLab issues for bugs. Anything tagged with "bug" and "help wanted" is open to whoever wants to implement it.

### Implement Features

Look through the GitLab issues for features. Anything tagged with "enhancement" and "help wanted" is open to whoever wants to implement it.

### Write Documentation

 could always use more documentation, whether as part of the official  docs, in docstrings, or even on the web in blog posts, articles, and such.

### Submit Feedback

The best way to send feedback [our issue page][gl-issues] on GitLab. If you are proposing a feature:

- Explain in detail how it would work.
- Keep the scope as narrow as possible, to make it easier to implement.
- Remember that this is a volunteer-driven project, and that contributions are welcome 😊

## Get Started!

Ready to contribute? Here's how to set yourself up for local development.

1. Fork the repo on GitLab.

2. Clone your fork locally:

   ```shell
   git clone git@gitlab.com:your_name_here/.git
   ```


3. Install the project dependencies with [uv](https://docs.astral.sh/uv/):

   ```shell
   sudo apt install git-lfs git-flow

   cd 
   uv sync
   ```

4. Create a branch for local development:

    ```shell
   git checkout develop
   git flow feature start name-of-your-bugfix-or-feature
   ```

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass our tests:

   ```shell
   uv run pytest -s -vv
   ```

6. Linting is done through [pre-commit](https://pre-commit.com). Provided you have the tool installed globally, you can run them all as one-off:

   ```shell
   uv run pre-commit run -a
   ```

   Or better, install the hooks once and have them run automatically each time you commit:

   ```shell
   uv run pre-commit install
   ```

7. Commit your changes and push your branch to GitHub:

   ```shell
   git add . # or specify files you want to add
   git commit -m "feat(something): your detailed description of your changes"
   # to bump the version number, use the `semantic-release` command:
   uv run semantic-release -v version --patch # or --minor or --major (and --noop for dry run)
   # now push your changes to the remote repository
   git flow feature publish name-of-your-bugfix-or-feature
   # to finish the feature branch, this will merge it into develop and delete the branch
   git flow feature finish name-of-your-bugfix-or-feature
   ```

   Note: the commit message should follow [the conventional commits](https://www.conventionalcommits.org). We run [`commitlint` on CI](https://github.com/marketplace/actions/commit-linter) to validate it, and if you've installed pre-commit hooks at the previous step, the message will be checked at commit time.



8. Submit a merge request through the GitLab website or using the GitLab CLI (if you have it installed):

   



## Pull Request Guidelines

We like to have the pull request open as soon as possible, that's a great place to discuss any piece of work, even unfinished. You can use draft pull request if it's still a work in progress. Here are a few guidelines to follow:

1. Include tests for feature or bug fixes.
2. Update the documentation for significant features.
3. Ensure tests are passing on CI.

## Tips

To run a subset of tests:

   ```shell
   uv run pytest -s -vv tests
   ```

## Making a new release

The deployment should be automated and can be triggered from the Semantic Release workflow in GitHub. The next version will be based on [the commit logs](https://python-semantic-release.readthedocs.io/en/latest/commit-log-parsing.html#commit-log-parsing). This is done by [python-semantic-release](https://python-semantic-release.readthedocs.io/en/latest/index.html) via a GitHub action.


[gl-issues]: https://gitlab.com/opensourcelab/cheminformatics//issues
