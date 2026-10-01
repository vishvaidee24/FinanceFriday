# Data Sources

| Dataset | V1 Provider | Cost |
|---|---|---:|
| Stock bars | Alpaca | Free tier |
| Options | Alpaca | Free/indicative initially |
| SEC filings | SEC EDGAR | Free |
| Fundamentals | SEC CompanyFacts | Free |
| Insider trades | SEC Form 4 | Free |
| Executive disclosures | U.S. Office of Government Ethics Form 278/278-T | Free |
| Historical executive trades | [Disclosed Capitol executive-branch-trades](https://github.com/disclosedcapitol/executive-branch-trades), derived from official OGE filings (CC BY 4.0) | Free |
| News | RSS / company IR | Free |
| Bonds | FINRA | Free where accessible |
| Reddit | Reddit API | Free where accessible |
| Kalshi | Public API | Free |
| Polymarket | Public API | Free |

Deferred paid feeds should be introduced behind provider interfaces.

See [INGESTIONS.md](INGESTIONS.md) for the current schedules, runners,
destinations, and raw archive paths.
