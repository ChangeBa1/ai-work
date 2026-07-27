"""Feature 015: page/element memory (overall_design.md §12/§13/§21.3).

- ``fingerprint``: pure page-fingerprint construction + similarity scoring.
- ``retrieval``: pure page/element matching helpers (template neighborhood).
- ``service``: persistence-backed facade consumed by the runtime and, later,
  by feature 016's replay player.
"""
