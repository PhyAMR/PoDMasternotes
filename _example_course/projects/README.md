# Example Course — Projects

In the live setup, every course's *Projects* landing page is built from
two sources:

- The link to the course's GitHub repository, configured per course in
  `Notes/_projects_github.yml`. Edit that file to point at your repo.
- The READMEs found under this directory, surfaced as sections on the
  Projects landing page (see `Notes/generate_listing.py`).

For an example course you usually don't have project deliverables yet,
so a single top-level `README.md` like this one is enough — it will be
inlined as the body of `<course>/projects.html`.

When you actually start a project, add a sub-directory here (one per
project) with its own `README.md`. The build script walks two levels
deep, so deeply nested vendored sub-tools won't accidentally appear on
the public page.
