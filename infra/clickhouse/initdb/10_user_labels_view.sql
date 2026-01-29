-- PolyTool: Centralized user dropdown labels for Grafana
-- Creates a view that provides consistent user labels across all dashboards

-- Drop existing view if it exists (for idempotent migrations)
DROP VIEW IF EXISTS polyttool.users_grafana_dropdown;

-- Create view with canonical label logic:
-- - If username exists: "@username (0x1234…abcd)"
-- - If username missing: "0x1234…abcd"
-- - Handles duplicates via argMaxIf on last_updated (prefers non-empty usernames)
-- - Filters out empty proxy_wallet rows
CREATE VIEW polyttool.users_grafana_dropdown AS
WITH
    argMaxIf(trimBoth(username), last_updated, trimBoth(username) != '') AS best_username,
    if(
        best_username != '' AND NOT startsWith(best_username, '@'),
        concat('@', best_username),
        best_username
    ) AS display_username
SELECT
    proxy_wallet AS __value,
    if(
        display_username != '',
        concat(
            display_username,
            ' (',
            left(proxy_wallet, 6),
            '…',
            right(proxy_wallet, 4),
            ')'
        ),
        concat(left(proxy_wallet, 6), '…', right(proxy_wallet, 4))
    ) AS __text
FROM polyttool.users
WHERE proxy_wallet != '' AND proxy_wallet IS NOT NULL
GROUP BY proxy_wallet
ORDER BY argMax(last_updated, last_updated) DESC;

-- Grant read access to Grafana
GRANT SELECT ON polyttool.users_grafana_dropdown TO grafana_ro;
