# Host maintenance

Manual runbook for the single-VPS topology in [`DEPLOY.md`](DEPLOY.md). These
checks are not installed by a deploy; apply them once on the host and verify
that cron and outbound mail work there. The disk alert uses cron's mail
delivery, so `MAILTO` must be a monitored address and the host must have a
working local mail transfer agent. Without mail delivery the check still runs,
but its alert cannot leave the host.

## Disk alert and weekly build-cache prune

Create `/etc/cron.d/amm-ds-portfolio-maintenance` as root, replacing the email
address first:

```cron
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=ops@example.com

# Alert at or above 85% disk usage; cron mails output only when over threshold.
*/15 * * * * root used=$(df -P / | awk 'NR == 2 { print $5 + 0 }'); if [ "$used" -ge 85 ]; then echo "Disk usage on / is ${used} percent (threshold 85)"; fi

# Remove dangling Docker build cache every Monday at 04:17 host time.
17 4 * * 1 root docker builder prune -f
```

The disk check emits mail every 15 minutes while usage remains at or above
85%. The prune removes dangling build cache, not tagged images; keep the
current and previous release images for rollback. Do not schedule a release
build at the same time as the weekly prune.

After installation, confirm the file is root-owned and mode `0644`, then test
mail delivery and inspect usage:

```bash
echo "portfolio disk-alert test" | mail -s "portfolio disk-alert test" ops@example.com
df -h /
sudo journalctl -u cron --since "15 min ago" --no-pager
```

For disk-pressure remediation and image-retention rules, use
[`HETZNER.md`](HETZNER.md). A cron alert complements the public uptime probe;
it does not replace it.
