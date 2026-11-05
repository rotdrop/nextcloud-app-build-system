# Consuming app repository lookup

When a task mentions a consuming app, use this mapping directly rather than
guessing a repository name or searching the account's repositories:

| App name | GitHub repository |
| --- | --- |
| bav | rotdrop/nextcloud-app-bav |
| cafevdb | rotdrop/cafevdb |
| cafevdbmembers | rotdrop/cafevdb-members |
| dokuwiki | rotdrop/nextcloud-app-dokuwiki |
| files_archive | rotdrop/nextcloud-app-files-archive |
| mail_roundcube | rotdrop/nextcloud-roundcube |
| pdf_downloader | rotdrop/nextcloud-app-pdf-downloader |
| redaxo | rotdrop/nextcloud-app-redaxo |

These are consumers of this shared build system, not directories in this
repository. In particular, `bav` and `dokuwiki` refer to the Nextcloud app
repositories above, not the similarly named `rotdrop/bav` and `rotdrop/dokuwiki`
repositories.

Query the resolved repository's current default branch when needed; do not
assume it is `main` or `master`. If a task names a specific branch, use that
branch instead. Read access does not imply write authorization in the current
session.

Keep this mapping consistent with the "Consuming app repositories" section
of `README.md` when repository names change.
