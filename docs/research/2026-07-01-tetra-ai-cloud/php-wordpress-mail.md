## 5. Hosting traditional PHP/WordPress/mail (the Plesk side)

_Research as of 2025-07; deep web research on how modern container-based OSS platforms
(Coolify, Dokploy) handle legacy PHP/WordPress + MySQL and mail, and how that coexists with
a Vercel-like container-deploy panel. Deliverability and Hetzner port-25 specifics are flagged
as the two highest-uncertainty areas._

### 5.1 Can Coolify / Dokploy run WordPress + PHP + MySQL/MariaDB?

Yes — both do this today as first-class one-click services, but only as **containerized
app+DB stacks**, not as a shared-hosting substrate.

- **Coolify** ships WordPress as a ready-to-deploy one-click service with two variants:
  "WordPress with MariaDB" (recommended) and "WordPress with MySQL"; the docs also recommend
  splitting into a standalone MySQL/MariaDB resource + "WordPress Without Database" so you unlock
  Coolify-managed **automatic backups**, which the combined bundle doesn't get
  (source: https://coolify.io/docs/services/wordpress ; https://hasto.pl/installing-and-configuring-wordpress-with-mysql-on-coolify/ , 2025).
- Coolify supports one-click **MySQL, MariaDB, PostgreSQL, MongoDB, Redis, KeyDB, DragonFly,
  ClickHouse** databases, and its v4 catalog is now ~280+ one-click services
  (source: https://coolify.io/docs/databases ; https://nextgrowth.ai/what-is-coolify/ , 2026).
- Arbitrary PHP apps run via **raw docker-compose paste** — Coolify auto-creates a shared
  network so services resolve each other by name, no manual network declaration
  (source: https://azdigi.com/en/blog/self-hosted/deploy-docker-compose-on-coolify-complex-multi-container-applications , 2025).
- **Dokploy** has the same shape: one-click templates for WordPress, Nextcloud, MySQL,
  MariaDB, PostgreSQL, MongoDB, Redis; native docker-compose; managed backups for those DBs;
  Traefik-issued Let's Encrypt certs. Its stock WordPress template is WordPress + MySQL 8.4
  (source: https://docs.dokploy.com/docs/templates/wordpress ; https://dokploy.com/features/application-deployment-platform , 2025).

**Where the container model does NOT fit "traditional" cPanel/Plesk shared PHP hosting.**
Coolify/Dokploy are app-per-stack PaaS, not site-per-account panels. The concrete gaps vs a
real Plesk/cPanel for "many small PHP sites with per-site isolation":

- **No per-site PHP-version selector / PHP-FPM tuning UI.** Plesk (since 10.4) and cPanel's
  MultiPHP/PHP-Selector let you pick a PHP version + toggle extensions (intl, imagick, opcache)
  **per domain/subscription**; Coolify's WordPress docs don't expose PHP version selection at all
  — you'd change the container base image instead
  (source: https://docs.plesk.com/en-US/obsidian/reseller-guide/understanding-service-plans-and-subscriptions/properties-of-hosting-plans-addons-and-subscriptions/hosting-parameters/php-settings.70987/ ;
  https://www.cantech.in/blog/plesk-vs-coolify/ , 2026; Coolify PHP-version selection: not mentioned in
  https://coolify.io/docs/services/wordpress ).
- **No true multi-tenant / reseller isolation.** Coolify has only `admin`/`member` roles, no
  per-service or action-level permissions, and **teams cannot share the same underlying server**
  — so you can't safely put multiple untrusted customers on one box the way shared hosting does.
  Multi-tenancy is a long-standing feature request, not a shipped capability
  (source: https://massivegrid.com/blog/coolify-multi-server-setup/ ;
  https://github.com/coollabsio/coolify/issues/77 ; https://github.com/coollabsio/coolify/discussions/1948 , 2025-2026).
- **No integrated email accounts, no DNS-zone editor, no per-domain FTP, no WordPress Toolkit.**
  These are the pillars of a Plesk/cPanel subscription; Coolify/Dokploy provide none of them
  natively — they are app+reverse-proxy+DB platforms. Multiple comparisons state plainly that
  Coolify "does not specialize in shared hosting" and is "application-centric rather than
  site-centric," targeting Git/Docker deployment, not classic domains/mailboxes/FTP
  (source: https://www.cantech.in/blog/coolify-vs-cpanel... → https://www.cantech.in/blog/cpanel-vs-coolify/ ;
  https://www.cantech.in/blog/plesk-vs-coolify/ , 2026).

**Takeaway:** Coolify/Dokploy give you WordPress + MySQL/MariaDB with backups and TLS out of the
box for a *handful of stacks you control*. They are not a drop-in for a Plesk box hosting dozens
of isolated customer sites with per-site PHP versions, mailboxes, DNS zones, and FTP. For Tetra
Host that means the "Plesk side" (mail, DNS, per-tenant isolation) has to come from the panel
layer + Mailcow/Cloudflare, not from Coolify itself — which matches the current architecture
(Coolify = sites/apps, Mailcow = mail, Cloudflare = DNS).

### 5.2 Mail hosting in a container world (Mailcow / Mailu / Docker mail)

- **Mailcow (docker-mailcow-dockerized)** is a Docker-Compose bundle of Postfix + Dovecot +
  Rspamd + ClamAV + SOGo webmail with a polished admin UI; positioned as the default for SMB
  with ~10–500 mailboxes; needs 2GB+ RAM. **Mailu** is a lighter compose stack (Postfix +
  Dovecot + Rspamd + Roundcube/SnappyMail + a small Python admin), lower footprint if you skip
  ClamAV, weaker admin/domain-admin UI, and "works well on Kubernetes." Stalwart is the newer
  all-in-one-binary contender
  (source: https://sumguy.com/self-hosted-email-mailcow-mailu-stalwart/ ;
  https://profor.pro/blog/self-hosted-email-2026-mailcow-stalwart-mailu/ , 2026).
- **Multi-tenancy:** both Mailcow and Mailu support multiple mail domains with domain-level
  admins, so per-tenant mail domains are feasible — but domain-admin power is thin in Mailu, and
  neither gives you the fine-grained reseller model of Plesk (uncertain: exact per-tenant quota /
  delegation limits vary by version — verify against the running Mailcow before promising tenant
  self-service) (source: https://sumguy.com/self-hosted-email-mailcow-mailu-stalwart/ , 2026).
- **The hard problems are NOT the software — they're IP reputation and DNS.** Every primary
  comparison converges on the same point: "None of them will save you from a bad IP or a
  misconfigured DNS record… deliverability is determined by your configuration and reputation,
  not the software," and "the hard part is warming the IP, keeping reverse DNS clean, and
  surviving Microsoft's silent blocks"
  (source: https://sumguy.com/self-hosted-email-mailcow-mailu-stalwart/ , 2026).
- **PTR/rDNS is now an SMTP-level requirement, not a nicety** (flagged — dates below are from
  secondary trackers; treat the exact month/threshold as approximate and re-verify against
  Google/Yahoo/Microsoft postmaster docs before relying on them):
  - Feb 2024: Google + Yahoo began requiring SPF+DKIM+DMARC, valid forward+reverse DNS (PTR),
    one-click unsubscribe, and a <0.3% spam-complaint rate for bulk senders (5,000+/day); the
    one-click-unsubscribe deadline slipped to June 2024
    (source: https://dmarcian.com/yahoo-and-google-dmarc-required/ ;
    https://www.mailgun.com/state-of-email-deliverability/chapter/yahoogle-bulk-senders/ , 2024-2025).
  - Reportedly May 2025 Microsoft enforced equivalent rules (550 5.7.15 rejections) and Nov 2025
    Gmail escalated missing-PTR from deferral to permanent 550 rejection — i.e. in 2026 a missing
    PTR is a hard bounce, not just a spam risk **(uncertain — single-source secondary claim; verify)**
    (source: https://netguardia.com/privacy/self-hosting/running-your-own-mail-server-in-2026-mailcow-mail-in-a-box-and-the-deliverability-problem/ , 2026).
  - Cleanest setup is **forward-confirmed reverse DNS** (FCrDNS): PTR hostname → A/AAAA →
    back to the same IP (source: https://mailtrap.io/blog/ptr-records/ , 2026).
- **Own-mail vs relay — the consensus recommendation:** run your own IMAP for *receiving*, but
  **relay outbound through a transactional ESP (Postmark / Amazon SES / Mailgun)** for anything
  that must land reliably; a fresh VPS IP reaching Gmail/Outlook consistently is "harder than it
  looks," and VPS IP ranges are distrusted by default. Postmark is repeatedly named as the
  deliverability-optimized choice (clean shared-IP pool, ~99% in 10s); SES is cheaper but pushes
  warmup/suppression/bounce/complaint handling onto you
  (source: https://netguardia.com/privacy/self-hosting/running-your-own-mail-server-in-2026-mailcow-mail-in-a-box-and-the-deliverability-problem/ ;
  https://powerdmarc.com/self-hosting-email/ ;
  https://postmarkapp.com/blog/transactional-email-providers , 2025-2026).

  **Recommendation for Tetra Host:** treat Mailcow as the receive/mailbox store and, per tenant,
  offer an outbound **smarthost/relay** through an ESP so a single bad-actor tenant or a cold
  Hetzner IP doesn't tank deliverability for everyone. Sell "mailboxes," not "raw SMTP egress."

### 5.3 Hetzner Cloud as the infrastructure

- **API / provisioning:** Hetzner Cloud has a full REST API covering servers, Floating IPs,
  Volumes, Firewalls, and Load Balancers, with sub-30s provisioning (usable for ephemeral
  workloads) (source: https://docs.hetzner.cloud/ ; https://betterstack.com/community/guides/web-servers/hetzner-cloud-review/ , 2026).
- **Pricing/value 2025-2026:** entry shared-vCPU instances start ~€3.79/mo (CX22); CX23 ~€5.49,
  Arm CAX11 ~€5.99; hourly billing with a monthly cap; block volumes €0.0572/GB/mo; snapshots
  €0.0143/GB/mo; automatic backups = 20% of instance price (7 retained). Widely regarded as the
  price/perf leader (source: https://www.hetzner.com/cloud/pricing/ ;
  https://costgoat.com/pricing/hetzner ; https://kuberns.com/blogs/hetzner-cloud-pricing/ , 2026).
- **Firewall / LB:** stateful cloud firewalls at no extra cost, assignable to many servers;
  Cloud Load Balancers billed hourly, do TLS termination and route into private Cloud Networks
  (source: https://www.hetzner.com/cloud/load-balancer/ ; https://docs.hetzner.com/cloud/load-balancers/ , 2026).
- **Port 25 / mail — the important caveat (well-confirmed, incl. Hetzner's own docs):** Hetzner
  **blocks outbound ports 25 and 465 by default on all cloud servers.** After you've been a
  customer for **one month and paid your first invoice**, you can file a limit request to unblock,
  decided case-by-case. **Port 587 is not blocked.** Blocking is enforced per account and follows
  the new owner on server transfer
  (source: https://docs.hetzner.com/cloud/servers/faq/ — direct quote: "we block ports 25 and 465
  by default on all cloud servers"; https://blog.hqcodeshop.fi/archives/553-Hetzner-outgoing-mail-SMTP-blocked-on-TCP25.html ,
  2025). **Implication:** self-hosted Mailcow on a fresh Hetzner box cannot send on 25 until
  unblocked — another reason to relay outbound (587/ESP) initially. **(Flagged uncertainty:** the
  exact 1-month/first-invoice gate and whether unblock is granted for a multi-tenant hosting use
  case is the biggest operational unknown — confirm with a live Hetzner support ticket before
  designing tenant-facing SMTP.)
- **IP reputation on Hetzner:** deliverability sources list Hetzner (alongside OVH, Vultr) among
  providers that "screen their address space," i.e. a *relatively* cleaner starting point than
  random VPS ranges — but still requires IP warmup and clean rDNS; no IP is trusted by default
  (source: https://netguardia.com/privacy/self-hosting/running-your-own-mail-server-in-2026-mailcow-mail-in-a-box-and-the-deliverability-problem/ , 2026).
- **Coolify on Hetzner:** commonly done in practice; Hetzner even publishes an editorial blog on
  Coolify as one-click self-hosting. (Note: that post is editorial — it is **not** an official
  Hetzner one-click Coolify product, and it does not mention mail/port 25)
  (source: https://www.hetzner.com/blog/one-click-self-hosting-with-coolify/ ;
  https://hostadvice.com/vps/coolify-hosting/ , 2026).

### 5.4 The architectural tension: Vercel-like ephemeral vs long-lived stateful PHP+MySQL+mail

The core mismatch: a Vercel/container mental model assumes **stateless, ephemeral, rebuild-on-push**
workloads, while WordPress/PHP + MySQL + mail are **long-lived and stateful** (persistent volumes,
DB durability, mailbox stores, IP reputation that must be *warmed and kept*, not recreated).

How OSS panels bridge it today:

- They **don't force everything to be ephemeral.** Coolify/Dokploy treat databases and volume-
  backed services as **persistent named resources with managed backups**, deployed alongside the
  stateless app containers, rather than tearing them down each deploy
  (source: https://coolify.io/docs/databases ; https://docs.dokploy.com/docs/templates/wordpress , 2025).
- The pragmatic split, echoed across 2025 sources: **Docker Compose for stateful, low-scale
  workloads (single-instance MySQL/Postgres, WordPress) because it's simpler and "honestly just as
  reliable"; Kubernetes/k3s only when you need distributed, scaling, public-facing services** —
  running a database in k8s adds StatefulSets/headless-services/PVC friction for little gain on a
  single node (source: https://compacthost.com/blog/container-orchestration-beyond-docker-when-to-consider-kuber/ ;
  https://flywp.com/blog/15654/docker-compose-vs-kubernetes-for-wordpress/ ;
  https://stanislas.blog/2025/04/moving-to-k8s/ , 2025).
- **k3s vs plain Docker when you must host BOTH modern apps AND legacy PHP/WordPress/mail:**
  - k3s pros: built-in local-path dynamic PV provisioning, runs from ~512MB RAM, IaC via
    version-controlled YAML, easy node migration (rsync /var/lib/rancher)
    (source: https://www.glukhov.org/post/2025/08/kubernetes-distributions-comparison/ ;
    https://stanislas.blog/2025/04/moving-to-k8s/ , 2025).
  - Plain Docker/Compose pros: far lower learning curve and less friction for the exact stateful
    single-instance workloads (MySQL, WordPress, and Mailcow — which *ships as compose* and is
    not designed to be k8s-native) that dominate the "Plesk side."
  - **Assessment for Tetra Host:** given that Coolify itself is Docker/Compose-based, Mailcow is
    Compose-based, and the stateful workloads are single-instance, **plain Docker (via Coolify) is
    the better fit than k3s** for the legacy PHP/WordPress/mail half. k3s only earns its complexity
    if/when the modern-app half needs multi-node scaling and self-healing across a fleet — and even
    then, mail (Mailcow) and per-tenant MySQL are usually left on dedicated Docker hosts, not in the
    cluster, precisely because of stateful + IP-reputation constraints.

**Net architectural conclusion.** The two worlds coexist by **not pretending mail/DB are
ephemeral**: keep the Vercel-like flow (Coolify: Git push → container → reverse proxy → TLS) for
apps/sites, but run mail and per-tenant databases as **long-lived, backed-up, pinned-IP Docker
services** — with **outbound mail relayed through an ESP** to sidestep Hetzner port-25 blocking and
VPS-IP reputation. The panel layer (Tetra Host) is what supplies the "Plesk-shaped" surface
(mailboxes, DNS zones, per-tenant isolation) that neither Coolify nor Dokploy provides on its own.

**Highest-uncertainty items to verify before building:** (1) Hetzner port-25 unblock policy for a
multi-tenant hosting use case — open a live ticket; (2) the exact 2025-2026 Gmail/Microsoft PTR
"hard-reject" dates/thresholds — confirm against official postmaster docs; (3) Mailcow/Mailu
per-tenant delegation limits — verify against the pinned version you deploy.
