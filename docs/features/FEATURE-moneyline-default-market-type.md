# Feature: Moneyline Default Market Type

Team-vs-team markets are now less likely to be labeled `unknown` when the intent is clearly a matchup winner market. This improves segment reporting while keeping classification conservative and explainable.

## Rule

When classifying `market_type`:

1. If slug/question contains spread indicators (`spread`, `handicap`), classify as `spread`.
2. Else if slug/question contains total indicators (`total`, `over/under`, `o/u`), classify as `total`.
3. Else if question matches `Will .* win`, classify as `moneyline` (existing rule).
4. Else apply default moneyline rule:
   - league is known (`league != "unknown"`),
   - slug/question contains matchup token (`vs` or `v`),
   - slug/question does not look like player props,
   - then classify as `moneyline`.
5. Otherwise classify as `unknown`.

## Edge Cases

- Unknown league + `vs` text remains `unknown`.
- Spread/handicap text always wins over matchup default.
- Total/over-under text always wins over matchup default.
- Prop-like wording blocks matchup default and stays `unknown`.
- Existing deterministic behavior is preserved; no network lookups and no new dependencies.
