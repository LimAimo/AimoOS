# AimoOS engineering rules

- Read DESIGN_SYSTEM.md and docs/OS_DESIGN.md before any visual change.
- The user-provided AimoChat Design System is the visual authority. Its chat,
  billing, community and web-only business rules do not introduce OS features.
- Keep all colors, radii and timings in aimo/theme.py, all icon drawing in
  aimo/icons.py and reusable controls in aimo/controls.py. Native Qt ports must
  preserve geometry-based segmented motion and clipped text inversion.
- Applications operate on real Linux files, processes and network engines.
  Disabled or unavailable OS capabilities must be represented accurately.
- Desktop applications run as the signed-in ordinary Linux user. Privileged
  first-run/account operations stay in the greeter and OS boot layer.
- Never commit credentials, user profiles, generated images, package caches,
  root filesystems, screenshots or build logs.
- Version authority is pyproject.toml. Update README and CHANGELOG together.
- Verify affected behavior, then commit locally using conventional commits.
  The user has explicitly requested source upload to their GitHub repository.
