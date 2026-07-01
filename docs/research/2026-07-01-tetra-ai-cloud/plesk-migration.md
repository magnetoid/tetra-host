# Plesk → Coolify/Mailcow/Cloudflare Migration Playbook (~30 sites)

Research report. All facts cited with URLs; primary sources (Plesk docs, Cloudflare docs, imapsync/mailcow docs) prioritized. Retrieved 2026-07-01. Coolify, Plesk Obsidian, imapsync 2.314 (2025-09-23), mailcow-dockerized current.

> **Scope note.** Source = one Hetzner VPS running Plesk Obsidian (Postfix + Dovecot mail, WordPress/PHP sites, DNS on Plesk and/or Cloudflare). Target = "Tetra AI Cloud": Coolify + Docker for sites, a dedicated Mailcow for mail, Cloudflare for DNS. Strategy = phased, side-by-side, per-site cutover, minimal downtime.

---

## 0. Executive summary & recommended shape

- **Decompose each Plesk subscription into 4 independent workstreams: files+DB (site), mail, DNS, TLS.** They cut over on different clocks. Do **not** treat "migrate a domain" as one atomic step — mail and web can (and should) move separately.
- **DNS is the cutover lever.** Get every zone onto Cloudflare *first* (as pure DNS, records unchanged, still pointing at the old Plesk box). Then each per-site cutover is just editing an A/AAAA (web) or MX (mail) record in one place — instant, reversible, low-TTL. This is the single most important enabler of low-downtime, per-site migration. ([Cloudflare full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/))
- **Sequence per site:** (1) zone on Cloudflare, TTLs low; (2) build the container + import DB on Coolify, test via hosts-file/preview; (3) initial mail pre-sync to Mailcow (runs for days, non-disruptive); (4) short maintenance window → final DB sync + final imapsync + flip A record + flip MX; (5) verify; (6) keep Plesk copy hot for rollback for ~1 week.
- **Biggest risk flagged up front — mail loopback:** while a domain's mail service is still enabled in Plesk, Plesk delivers same-domain mail *locally regardless of MX*, and can loop mail back to itself. You must explicitly disable the mail service for a domain in Plesk at mail-cutover, or split delivery breaks. ([Plesk: mail loops back to myself](https://support.plesk.com/hc/en-us/articles/12377859330455-Mail-delivery-to-an-external-domain-from-Plesk-server-fails-mail-loops-back-to-myself); [Plesk forum: external mail server not supported while local mail enabled](https://talk.plesk.com/threads/force-same-domain-emails-to-use-mx-records.375610/))
- **Realistic effort:** a plain WordPress + one DB + a handful of mailboxes ≈ **2–4 hours hands-on** (much of it unattended sync/propagation). Custom PHP apps, large mail stores, or bespoke Plesk config (cron, custom PHP-FPM, mod_rewrite quirks) push to a day. There is **no turnkey Plesk→container tool** — see §6.

---

## 1. What a Plesk site consists of, and how to extract it programmatically

A Plesk **subscription** (≈ a hosting plan bound to a main domain, possibly with add-on domains/subdomains) bundles: docroot files, PHP version/handler, one or more MySQL/MariaDB databases, mail accounts + maildirs, DNS zone, SSL/TLS certs, cron/scheduled tasks, and per-domain web-server config.

### 1a. Enumerate everything — Plesk REST API (`:8443/api/v2`)

The modern, scriptable inventory surface. Base URL `https://<host>:8443/api/v2/<endpoint>`. ([About REST API](https://docs.plesk.com/en-US/obsidian/api-rpc/about-rest-api.79359/); [How to manage Plesk via REST API](https://support.plesk.com/hc/en-us/articles/12377322315159-How-to-manage-Plesk-via-REST-API))

- **Auth:** basic (`--user root:password`) or create an API key: `POST :8443/api/v2/auth/keys`, then send `X-API-Key: <key>` on subsequent calls. CLI equivalent: `plesk bin secret_key -c -ip-address <ip>`. ([How to manage Plesk via REST API](https://support.plesk.com/hc/en-us/articles/12377322315159-How-to-manage-Plesk-via-REST-API))
- **List domains:** `GET :8443/api/v2/domains` → JSON with `id`, `name`, `ascii_name`, `guid`, `hosting_type`, created date. ([About REST API](https://docs.plesk.com/en-US/obsidian/api-rpc/about-rest-api.79359/))
- **Run any `plesk bin` utility remotely** via the CLI gateway: `POST :8443/api/v2/cli/<utility>/call` with the args as JSON. This is the escape hatch for anything the typed REST endpoints don't expose (service plans, per-domain PHP settings, DB lists, subscription details). ([How to manage Plesk via REST API](https://support.plesk.com/hc/en-us/articles/12377322315159-How-to-manage-Plesk-via-REST-API))

Use this to build a **migration manifest** CSV: one row per domain with docroot path, PHP version, DB name(s), mailbox list, cert, cron.

### 1b. Component-by-component extraction

| Component | Where it lives / how to extract |
|---|---|
| **Docroot / files** | `/var/www/vhosts/<domain>/httpdocs` (Plesk default vhost layout). Copy with `rsync -a` or tar. |
| **PHP version/handler** | Per-domain in Plesk; read via `plesk bin site --info <domain>` or `plesk bin domain --info`. **You must match this in the container** (see §2 pitfalls). |
| **Databases** | List: `plesk bin database --info <domain>` / via CLI-over-REST. Dump one DB: `plesk db dump "<dbname>"` or `MYSQL_PWD=$(cat /etc/psa/.psa.shadow) mysqldump -u admin <db>`. ([Backup all MySQL/MariaDB via CLI](https://support.plesk.com/hc/en-us/articles/12377216464279-How-to-backup-all-MySQL-MariaDB-databases-via-a-command-line-interface-in-Plesk-for-Linux); [Exporting/importing DB dumps](https://www.plesk.com/kb/docs/exporting-and-importing-database-dumps/)) |
| **Mail accounts** | Enumerate via REST/CLI (`plesk bin mail --info`). Maildirs on disk (see §3). |
| **DNS zone** | Plesk holds a per-domain zone; export records and recreate in Cloudflare (§4). |
| **SSL/TLS certs** | Stored per-domain in Plesk. In the target you **re-issue via Let's Encrypt** (Coolify + Cloudflare do this automatically) rather than migrating certs — simpler and avoids key handling. |
| **Cron / scheduled tasks** | Per-domain scheduled tasks in Plesk (crontab under the domain's system user). Enumerate and re-create as Coolify scheduled tasks / container cron. Easy to miss — audit explicitly. |

### 1c. `pleskbackup` as a belt-and-suspenders extractor

`plesk bin pleskbackup` backs up **user content (files), databases, and email messages**, optionally server settings; log files can be excluded. Per-subscription:

```
plesk bin pleskbackup --domains-name <domain> -output-file /path/domain.tar
# or by id:
plesk bin pleskbackup --domains-id <ID>   -output-file /tmp/domain1.tar
```

Options: `-compression-level maximum`, `-incremental`, `-s 3G` (split), FTP/remote target via `-output-file ftp://...` with `PLESK_BACKUP_PASSWORD`/`FTP_PASSWORD` env vars. Format is a **tar** archive (Plesk's own layout — designed for Plesk-to-Plesk restore, *not* a clean drop-in for containers). ([pleskbackup docs](https://docs.plesk.com/en-US/obsidian/cli-linux/using-command-line-utilities/pleskbackup-backing-up-content-and-configuration.74260/); [Exporting backup files](https://docs.plesk.com/en-US/obsidian/advanced-administration-guide-linux/backing-up-restoring-and-migrating-data/backing-up-data/exporting-backup-files.68841/))

> **Recommendation:** keep a `pleskbackup` per subscription as a *safety archive*, but drive the actual container build from **direct `rsync` of the docroot + `mysqldump` of the DB** — cleaner, inspectable, and container-friendly. The Plesk tar is awkward to unpack into `/var/www/html`. Note the DNS zone and cert are **not** reliably in the content backup, so extract those separately.

---

## 2. Migrating WordPress/PHP sites into containers (Coolify)

**Coolify has no built-in host-to-host app migration** — you deploy the app fresh on the target and copy DB + volumes yourself. ([Coolify migrate apps](https://coolify.io/docs/knowledge-base/how-to/migrate-apps-different-host))

### 2a. Recommended WordPress shape on Coolify (2025)

Deploy **WordPress and the database as two separate resources**, not the bundled one — this unlocks Coolify's automated DB backups and independent lifecycle. ([hasto.pl WP+MySQL on Coolify, 2025](https://hasto.pl/installing-and-configuring-wordpress-with-mysql-on-coolify/); [Coolify Docker Compose](https://coolify.io/docs/knowledge-base/docker/compose))

Concrete steps (from the 2025 guide):
1. New project → add **"WordPress Without Database"** + **MySQL/MariaDB** resources. Keep DB internal (no public port). ([hasto.pl](https://hasto.pl/installing-and-configuring-wordpress-with-mysql-on-coolify/))
2. Enable **"Connect to predefined Network"** on the WordPress resource so the two containers can talk; use the **MySQL container name** as `WORDPRESS_DB_HOST` (not localhost). ([hasto.pl](https://hasto.pl/installing-and-configuring-wordpress-with-mysql-on-coolify/))
3. Create the DB/user:
   ```
   docker exec -it <MYSQL_CTR> mysql -uroot -p'<ROOT_PW>' -e "CREATE DATABASE wordpress;"
   docker exec -it <MYSQL_CTR> mysql -uroot -p'<ROOT_PW>' -e "GRANT ALL PRIVILEGES ON wordpress.* TO 'mysql'@'%'; FLUSH PRIVILEGES;"
   ```
4. **Persistent uploads/files:** map a host dir to the WP docroot in the compose:
   ```yaml
   volumes:
     - '/var/wordpress-sites/website.com:/var/www/html'
   ```
   (`mkdir -p` it first; it must be writable by the container web user.) Coolify's persistent-volume/file feature keeps this in sync. ([hasto.pl](https://hasto.pl/installing-and-configuring-wordpress-with-mysql-on-coolify/); [Coolify volume migration note](https://coolify.io/docs/knowledge-base/how-to/migrate-apps-different-host))
5. Set the **domain + SSL** in Coolify (Let's Encrypt / Cloudflare). For HTTPS behind a proxy, add `$_SERVER['HTTPS']='on';` to `wp-config.php` or WP may misbehave. ([hasto.pl](https://hasto.pl/installing-and-configuring-wordpress-with-mysql-on-coolify/))

### 2b. Importing the existing site

1. `rsync` the Plesk docroot into the mounted `/var/www/html` volume (or just `wp-content/` if using a stock WP image and re-installing core at matching version).
2. `wp db import dump.sql` (or `mysql < dump.sql`) into the container DB.
3. **URL/domain fixups — use `wp search-replace`, never raw SQL.** WP stores serialized PHP; a naive `UPDATE` breaks byte counts silently. `wp search-replace` unserializes, replaces, re-serializes correctly. ([WP-CLI search-replace docs](https://developer.wordpress.org/cli/commands/search-replace/); [Gatilab guide](https://gatilab.com/wp-cli-search-replace/))
   ```
   wp db export backup-before.sql            # only rollback is this backup
   wp search-replace 'http://old' 'https://new' --precise --skip-columns=guid --dry-run
   wp search-replace 'http://old' 'https://new' --precise --skip-columns=guid
   ```
   Confirm `siteurl` and `home` in `wp_options` both hold the new `https://` URL and are identical. ([webdock Plesk→migration](https://webdock.io/en/docs/how-guides/migration-guides/how-move-wordpress-site-plesk-webdock))
4. **WP-CLI in Coolify:** you can add the `wordpress:cli` image to the compose, but users report the cli container restart-looping under Coolify — a common workaround is to `docker exec` wp-cli into the running WP container instead, or run it as a one-shot. ([Coolify WP-CLI discussion #3990](https://github.com/coollabsio/coolify/discussions/3990))

### 2c. Static vs dynamic

- **Truly static or brochure sites** (or WP you're willing to freeze): consider snapshotting to static HTML and serving as a Coolify static/Nginx app — no PHP, no DB, near-zero attack surface and cost. Best for sites that don't change.
- **Dynamic WP/PHP:** container + managed DB as above. Persistent storage (uploads, `wp-content/uploads`, any user-generated files) **must** be on a Coolify persistent volume or it's lost on redeploy.

### 2d. Pitfalls (flagged)

- ⚠️ **PHP version mismatch.** Match the container PHP to the Plesk site's PHP version; themes/plugins break on version drift. Extract the Plesk per-domain PHP version first. ([webdock](https://webdock.io/en/docs/how-guides/migration-guides/how-move-wordpress-site-plesk-webdock))
- ⚠️ **File permissions.** Files 644/640, dirs never 777 (not even uploads), `wp-config.php` 440/400. Container web-user UID must own the volume. ([Plesk WP file permissions](https://www.plesk.com/blog/various/wordpress-file-permissions/); [webdock](https://webdock.io/en/docs/how-guides/migration-guides/how-move-wordpress-site-plesk-webdock))
- ⚠️ **`.htaccess`/mod_rewrite.** Plesk uses Apache; stock WP containers/Coolify proxy may use Nginx — pretty-permalink rewrites and custom `.htaccess` rules need porting.
- ⚠️ **Hardcoded paths & absolute URLs** in theme/plugin config, wp-config constants (`WP_HOME`, `WP_SITEURL`), and cron.
- ⚠️ **Persistent-volume redeploy loss** if uploads aren't on a declared volume.
- ⚠️ **Plesk-specific cron jobs** (backups, WP-Cron replacements) silently dropped unless re-created.

---

## 3. Mail migration: Plesk Dovecot → dedicated Mailcow

### 3a. Where Plesk mail lives

Default maildir root is `/var/qmail/mailnames` (path is `PLESK_MAILNAMES_D` in `/etc/psa/psa.conf`), even under Postfix+Dovecot. Structure: `/var/qmail/mailnames/<domain>/<user>/Maildir/{cur,new,tmp}` plus subfolders. Dovecot uses `mail_location = maildir:/var/qmail/mailnames/%Ld/%Ln/Maildir`. ([Where mailboxes are located](https://support.plesk.com/hc/en-us/articles/12377452024087-Where-are-mailboxes-located-on-a-Plesk-server); [Change default mailbox location](https://support.plesk.com/hc/en-us/articles/12377869111319--How-to-change-default-location-of-mailboxes-in-Plesk-for-Linux))

You **do not** copy maildirs directly (UID/format/index mismatch, fragile). Use **IMAP-to-IMAP sync** instead.

### 3b. imapsync (the tool Mailcow itself uses)

imapsync (Perl, latest release **2.314, 2025-09-23**) does incremental, restartable IMAP→IMAP transfer preserving folder hierarchy and flags, no duplicates. Mailcow bundles imapsync inside its Dovecot container and exposes it as **Sync Jobs** in the UI. ([imapsync official](https://imapsync.lamiral.info/); [mailcow sync jobs migration](https://docs.mailcow.email/post_installation/firststeps-sync_jobs_migration/))

Canonical single-mailbox command:
```
imapsync \
  --host1 old-plesk-host --user1 user@dom --password1 'pw' --ssl1 \
  --host2 mailcow-host   --user2 user@dom --password2 'pw' --tls2 \
  --automap
```
Reliability flags: `--ssl`/`--tls`, `--automap` (folder mapping), `--addheader` (track transferred), `--dry` (test). ⚠️ `--delete2` is destructive on the *destination* — avoid during migration. ([imapsync official](https://imapsync.lamiral.info/))

**Many mailboxes:** loop a CSV of credentials with the provided `sync_loop_unix.sh` + `file.txt`. ([imapsync official](https://imapsync.lamiral.info/))

**Mailcow Sync Jobs (UI-driven, per mailbox):** Admin → *E-Mail → Configuration → Sync jobs*; fill source Host, Port, encryption (TLS≈143 / SSL≈993 / PLAIN discouraged), Username, Password, target mailbox. Repeatable/schedulable so it re-runs as delta syncs; verify by logging into the target mailbox; disable/delete the job when done. ([mailcow sync jobs](https://docs.mailcow.email/post_installation/firststeps-sync_jobs_migration/))

### 3c. Mail cutover strategy (minimize lost mail)

1. **Provision each domain in Mailcow ahead of time:** *Configuration → Mail setup → Domains → Add Domain* (bare `dom.com`, no `mail.` prefix), create all mailboxes with the same addresses. ([Mailcow DNS/setup](https://docs.mailcow.email/getstarted/prerequisite-dns/))
2. **Pre-seed:** run imapsync/Sync Jobs against live Plesk mail for **days** before cutover. Non-disruptive — mail still flows to Plesk. Repeat runs only copy deltas.
3. **DKIM ahead of time:** generate the 2048-bit DKIM key in Mailcow (*Configuration → Domains → DKIM*) and publish `<selector>._domainkey` TXT. ⚠️ **Selector must match exactly** (if Mailcow says `dkim`, record is `dkim._domainkey`) or DKIM silently fails. Publish SPF + DMARC manually. Google guidance: have DKIM+SPF live ≥48h before relying on DMARC. ([Mailcow DNS config](https://mailflowauthority.com/self-hosted-smtp/mailcow-dns-configuration); [Kentel DKIM/SPF/DMARC](https://www.kentel.dev/articles/dkim-spf-dmarc-mailcow-setup-guide))
4. **Cutover window (per domain):**
   a. Run a **final imapsync** delta.
   b. In **Plesk, disable the mail service for that domain** — otherwise Plesk keeps delivering same-domain mail locally and can loop it back regardless of MX. ⚠️ **This is the #1 mail gotcha.** ([Plesk mail loops back](https://support.plesk.com/hc/en-us/articles/12377859330455-Mail-delivery-to-an-external-domain-from-Plesk-server-fails-mail-loops-back-to-myself); [Plesk: local-vs-external delivery not supported](https://talk.plesk.com/threads/force-same-domain-emails-to-use-mx-records.375610/))
   c. **Flip MX** (and mail A/`autodiscover`/`autoconfig`) in Cloudflare to Mailcow. Low TTL (300s) makes this near-instant.
   d. Run **one more imapsync** after MX flip to catch mail that hit Plesk during propagation.
5. **Verify:** send to `check-auth@verifier.port25.com`; confirm SPF/DKIM/DMARC pass; score on mail-tester.com (aim 9–10/10). Set correct **PTR/rDNS** at Hetzner for the Mailcow IP. ([Mailcow DNS config](https://mailflowauthority.com/self-hosted-smtp/mailcow-dns-configuration))
6. ⚠️ **SPF must list the Mailcow sending IP**, not the old Plesk IP — change server, change SPF or mail breaks. ([Kentel guide](https://www.kentel.dev/articles/dkim-spf-dmarc-mailcow-setup-guide))

> **Zero-loss note:** IMAP sync only moves *stored* mail; the gap is in-flight SMTP during MX propagation. Low TTL + the post-cutover delta sync + keeping Plesk mail reachable (queue draining) closes it. Don't shut down Plesk mail immediately.

---

## 4. DNS migration & cutover (Cloudflare)

### 4a. Move zones onto Cloudflare first (records unchanged)

Add each zone in Cloudflare (Full setup); Cloudflare scans and imports existing records — **verify the imported set matches the Plesk zone exactly** (A, AAAA, CNAME, MX, TXT/SPF/DKIM/DMARC, SRV) before delegating. Change nameservers at the registrar to the assigned Cloudflare NS. At this stage records still point at the Plesk box, so nothing moves — you've only relocated *control* of DNS to one editable place. ([Cloudflare full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/); [Nameserver options](https://developers.cloudflare.com/dns/nameservers/nameserver-options/))

⚠️ **DNSSEC:** if active at the registrar, **disable DNSSEC before changing nameservers** or the domain can go unreachable; re-enable via Cloudflare afterward. ([Cloudflare DNSSEC](https://developers.cloudflare.com/dns/dnssec/))

### 4b. Lower TTLs before any content/mail cutover

24–48h before a site/mail flip, set the relevant records' TTL to **300s** so the actual cutover propagates in minutes. (Note: the *NS* delegation TTL is controlled by the TLD registry, typically 24–48h — that's why you relocate the zone to Cloudflare *well ahead*, decoupled from per-site cutovers.) After stability, raise TTLs back to ~3600s. ([Cloudflare full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/); [Mailcow DNS TTL guidance](https://mailflowauthority.com/self-hosted-smtp/mailcow-dns-configuration))

### 4c. Per-site cutover & rollback

- **Web:** change A/AAAA (and `www` CNAME) from Plesk IP → Coolify IP. Cloudflare-proxied (orange cloud) once TLS is confirmed on the target.
- **Mail:** change MX + mail A/autodiscover → Mailcow.
- **Verify:** `dig`, MXToolbox, curl the site through the new IP; check SSL.
- **Rollback:** because it's one record at low TTL, revert to the Plesk IP/MX in minutes. **Keep the Plesk copy running** until you've verified for days.

---

## 5. Phased coexistence strategy (running both platforms during a 30-site migration)

### Phase 0 — Foundation (once)
- Stand up Coolify host + Mailcow host on Tetra AI Cloud (separate IPs; Mailcow wants its own IP + PTR).
- Build the **migration manifest** (§1a): 30 rows × {docroot, PHP ver, DBs, mailboxes, DNS records, cron, cert}.
- Move **all** zones to Cloudflare as pure DNS, records unchanged, delegation switched. Disable DNSSEC first where present. Verify parity per zone. ([Cloudflare full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/))

### Phase 1 — Per-site build (parallelizable, non-disruptive)
- For each site: create Coolify WP+DB resources, rsync files, import DB, `wp search-replace`, test via a hosts-file override or Coolify preview URL. Nothing public changes.
- Provision the domain + mailboxes in Mailcow; publish DKIM/SPF/DMARC (records live but not authoritative for delivery until MX flips).
- Start imapsync pre-seed (runs for days).

### Phase 2 — Per-site cutover (short window each)
- Lower TTLs 24–48h prior.
- Web flip: final DB sync → change A record → verify → done. (Web has no local-delivery gotcha; it's clean.)
- Mail flip: final imapsync → **disable Plesk domain mail service** → change MX → post-flip delta imapsync → verify auth/deliverability.

### Phase 3 — Stabilize & decommission
- Watch each site/mailbox ~1 week; Plesk copy stays hot for rollback.
- Raise TTLs back up. Re-enable DNSSEC via Cloudflare.
- Only after all 30 verified: decommission the Plesk VPS.

### Coexistence hazards (flagged)
- ⚠️ **Mail-port conflict / split delivery.** You are **not** trying to split a single domain across Plesk and Mailcow simultaneously — migrate a domain's mail wholesale at cutover. Per-domain, disable Plesk's mail service at flip to stop local delivery/loopback. Mixed same-domain delivery is explicitly unsupported by Plesk. ([Plesk forum](https://talk.plesk.com/threads/force-same-domain-emails-to-use-mx-records.375610/); [Plesk mail loops](https://support.plesk.com/hc/en-us/articles/12377859330455-Mail-delivery-to-an-external-domain-from-Plesk-server-fails-mail-loops-back-to-myself))
- ⚠️ **Two servers sending as the same domain** during transition → keep SPF authorizing *both* IPs only if genuinely both send; otherwise flip cleanly. Simplest: mail moves atomically per domain.
- ⚠️ **Cloudflare proxy + mail records:** never orange-cloud MX/mail hostnames; keep mail A records DNS-only (grey cloud).
- ⚠️ **Shared IP reputation:** new Mailcow IP has no sending reputation — warm up, set PTR, monitor DMARC aggregate reports early.

---

## 6. Tooling & realistic effort

**No turnkey Plesk→container migrator exists.** Coolify explicitly has no host-to-host app migration; you deploy fresh + copy DB/volumes. ([Coolify migrate apps](https://coolify.io/docs/knowledge-base/how-to/migrate-apps-different-host)) Plesk's own **Migrator** is Plesk→Plesk only. ([Plesk migrator commands](https://support.plesk.com/hc/en-us/articles/12388260143127-How-to-perform-a-general-Plesk-to-Plesk-server-migration-via-Plesk-Migrator-commands))

Assemble from proven building blocks (all OSS/standard):
- **Inventory:** Plesk REST API `:8443/api/v2` + `/cli/*/call` gateway → generate the manifest. ([REST API](https://docs.plesk.com/en-US/obsidian/api-rpc/about-rest-api.79359/))
- **Files:** `rsync -a`. **DB:** `mysqldump` / `plesk db dump`. **Safety archive:** `pleskbackup` per subscription.
- **WordPress:** WP-CLI (`wp db import`, `wp search-replace`). ([WP-CLI](https://developer.wordpress.org/cli/commands/search-replace/))
- **Mail:** imapsync 2.314 (loop over CSV) or Mailcow Sync Jobs. ([imapsync](https://imapsync.lamiral.info/); [mailcow](https://docs.mailcow.email/post_installation/firststeps-sync_jobs_migration/))
- **Target:** Coolify (Docker Compose resources, persistent volumes, scheduled backups to S3, Let's Encrypt). ([Coolify compose](https://coolify.io/docs/knowledge-base/docker/compose))
- **DNS:** Cloudflare API/Terraform to bulk-import zones & records.

**Effort per site (hands-on, excluding unattended sync/propagation):**
- Static/brochure or freeze-to-static: ~1–2h.
- Standard WP + 1 DB + few mailboxes: ~2–4h.
- Custom PHP app, large mail store, heavy Plesk-specific config: up to ~1 day.
- 30 sites, one operator, batched in waves of ~5 with overlapping pre-seed: on the order of **2–4 weeks** wall-clock at a careful pace, most of it waiting on syncs/propagation rather than active work.

**Tetra-specific opportunity:** this repo already wraps Coolify + Cloudflare + Mailcow behind `/api/v1`. The migration manifest → per-site build → cutover checklist maps cleanly onto a "Migrations" module (Plesk inventory importer + a per-site state machine driving the existing Coolify/DNS/Mailcow services). That would turn this playbook into a first-class product feature rather than a one-off ops run.

---

## Per-site migration checklist (copy per domain)

**Prep**
- [ ] Manifest row complete: docroot, PHP version, DB name(s), mailbox list, DNS records, cron, cert
- [ ] Zone on Cloudflare, records verified identical, delegation live (DNSSEC disabled if it was on)
- [ ] `pleskbackup` safety archive taken

**Build (non-disruptive)**
- [ ] Coolify WP + separate DB resource created; internal network connected; DB host = container name
- [ ] Persistent volume mounted for `/var/www/html` + uploads
- [ ] Files rsynced; DB imported; PHP version matched
- [ ] `wp search-replace old→new --precise --skip-columns=guid` run; `siteurl`/`home` correct & identical
- [ ] File perms fixed (dirs !=777, `wp-config.php` 440/400); `.htaccess`/rewrites ported
- [ ] Tested via hosts-file/preview; TLS issues on target
- [ ] Mailcow: domain + all mailboxes created; DKIM key generated; DKIM/SPF/DMARC published (correct selector)
- [ ] imapsync pre-seed running (repeat deltas)

**Cutover window**
- [ ] TTLs lowered to 300s ≥24h earlier
- [ ] Final DB sync (web) + final imapsync delta (mail)
- [ ] ⚠️ Plesk domain **mail service disabled** (stop local delivery/loopback)
- [ ] A/AAAA → Coolify IP; MX + mail A/autodiscover → Mailcow
- [ ] Post-flip imapsync delta (catch mail that hit Plesk during propagation)

**Verify & stabilize**
- [ ] Site loads over HTTPS via new IP; forms/login/uploads work
- [ ] `dig`/MXToolbox correct; `check-auth@verifier.port25.com` + mail-tester ≥9/10; PTR set
- [ ] Monitor ~1 week; Plesk copy kept hot for rollback
- [ ] TTLs raised back; DNSSEC re-enabled via Cloudflare
- [ ] Site marked done in manifest

---

## Sources

- Plesk — [About REST API](https://docs.plesk.com/en-US/obsidian/api-rpc/about-rest-api.79359/); [How to manage Plesk via REST API](https://support.plesk.com/hc/en-us/articles/12377322315159-How-to-manage-Plesk-via-REST-API); [pleskbackup CLI](https://docs.plesk.com/en-US/obsidian/cli-linux/using-command-line-utilities/pleskbackup-backing-up-content-and-configuration.74260/); [Exporting backup files](https://docs.plesk.com/en-US/obsidian/advanced-administration-guide-linux/backing-up-restoring-and-migrating-data/backing-up-data/exporting-backup-files.68841/); [Backup MySQL/MariaDB via CLI](https://support.plesk.com/hc/en-us/articles/12377216464279-How-to-backup-all-MySQL-MariaDB-databases-via-a-command-line-interface-in-Plesk-for-Linux); [Exporting/importing DB dumps](https://www.plesk.com/kb/docs/exporting-and-importing-database-dumps/); [Where mailboxes are located](https://support.plesk.com/hc/en-us/articles/12377452024087-Where-are-mailboxes-located-on-a-Plesk-server); [Change default mailbox location](https://support.plesk.com/hc/en-us/articles/12377869111319--How-to-change-default-location-of-mailboxes-in-Plesk-for-Linux); [Mail loops back to myself](https://support.plesk.com/hc/en-us/articles/12377859330455-Mail-delivery-to-an-external-domain-from-Plesk-server-fails-mail-loops-back-to-myself); [Force MX / external mail not supported (forum)](https://talk.plesk.com/threads/force-same-domain-emails-to-use-mx-records.375610/); [Plesk Migrator](https://support.plesk.com/hc/en-us/articles/12388260143127-How-to-perform-a-general-Plesk-to-Plesk-server-migration-via-Plesk-Migrator-commands); [WP file permissions](https://www.plesk.com/blog/various/wordpress-file-permissions/)
- WordPress on Coolify — [hasto.pl WP+MySQL on Coolify (2025)](https://hasto.pl/installing-and-configuring-wordpress-with-mysql-on-coolify/); [Coolify Docker Compose](https://coolify.io/docs/knowledge-base/docker/compose); [Coolify migrate apps](https://coolify.io/docs/knowledge-base/how-to/migrate-apps-different-host); [Coolify WP-CLI discussion](https://github.com/coollabsio/coolify/discussions/3990); [webdock Plesk→migration](https://webdock.io/en/docs/how-guides/migration-guides/how-move-wordpress-site-plesk-webdock)
- WP-CLI — [search-replace docs](https://developer.wordpress.org/cli/commands/search-replace/); [Gatilab guide](https://gatilab.com/wp-cli-search-replace/)
- Mail — [imapsync official (2.314)](https://imapsync.lamiral.info/); [mailcow sync jobs migration](https://docs.mailcow.email/post_installation/firststeps-sync_jobs_migration/); [mailcow DNS prerequisites](https://docs.mailcow.email/getstarted/prerequisite-dns/); [Mailcow DNS config (MX/SPF/DKIM/DMARC/PTR)](https://mailflowauthority.com/self-hosted-smtp/mailcow-dns-configuration); [Kentel DKIM/SPF/DMARC guide](https://www.kentel.dev/articles/dkim-spf-dmarc-mailcow-setup-guide)
- DNS — [Cloudflare full setup / change nameservers](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/); [Cloudflare nameserver options](https://developers.cloudflare.com/dns/nameservers/nameserver-options/); [Cloudflare DNSSEC](https://developers.cloudflare.com/dns/dnssec/)

*Retrieved 2026-07-01.*
