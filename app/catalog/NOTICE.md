# App catalog: provenance

`templates.json` is Tetra Host's one-click app catalog. It ships with the panel; nothing is
downloaded at runtime.

The templates and the logos in `apps/web/public/catalog/logos/` were derived from the
open-source [coollabsio/coolify](https://github.com/coollabsio/coolify) service templates,
licensed under the Apache License 2.0. Logos remain the trademarks of their respective
projects and are used only to identify them.

Templates use `SERVICE_*` placeholders (`SERVICE_PASSWORD_DB`, `SERVICE_FQDN_APP`, …) that the
engine fills in at install time; see `app/services/app_catalog.py`.

Regenerate with `python scripts/catalog/build_catalog.py <export.json> --logos <dir>`.
