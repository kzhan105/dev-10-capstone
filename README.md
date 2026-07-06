# Hearthstone Minions — Capstone Project

A interactive dashboard exploring what actually makes a Hearthstone minion card competitive.

---

## Project Summary

Hearthstone is a digital collectible card game by Blizzard Entertainment. Each minion card has a mana cost, attack, health, class, race (tribe), and sometimes a keyword mechanic like Rush, Divine Shield, or Reborn. This project asks: **do the mechanics, races and numbers printed on the card predict how well it actually performs in competitive play?**

**Hypothesis:** Minions with strong keyword synergies or strong race synergies outperform the field in average deck win rate, while raw mana cost alone has little to no relationship with competitive performance.

---

## Questions Asked

1. Does a minion's mana cost correlate with its competitive win rate?
2. Which keyword mechanics appear most in high-performing decks?
3. Which minion races (tribes) see the strongest competitive performance?
4. Are the most-played minions also the highest win-rate minions, or do popularity and performance diverge?
5. Which class has the highest average deck win rate?
6. How has class popularity in ranked decks changed over 8 years of Hearthstone history?
7. Which deck archetypes were most dominant historically?

---

## Datasets

**Primary Dataset**
> samfo1. (2024). *Hearthstone minions stats and popularity* [Dataset]. Kaggle.
> https://www.kaggle.com/datasets/samfo1/hearthstone-minions-stats-and-popularity
> Accessed June 2026.

- 3,025 collectible Hearthstone minion cards
- 131 columns including card design attributes (cost, attack, health, class, race, rarity) and competitive performance metrics from HSReplay (deck inclusion rate, average copies, deck win rate, times played)
- Reflects the early 2024 competitive meta — not the current set
- Class, rarity, and race stored as numeric codes requiring decoding

**Supplementary Dataset**
> Crowder, S. (2022). *8 Years of Hearthstone Decks* [Dataset]. Kaggle.
> https://www.kaggle.com/datasets/sarahcrowder/8-years-of-hearthstone-decks
> Accessed June 2026.

- 668,000+ ranked deck submissions to Hearthpwn from 2013–2022
- Filtered to ~250k rows after removing non-ranked decks and Unknown archetypes
- Provides historical class popularity and archetype trend data
- Cannot be directly joined to the primary dataset due to different time periods

---

## ETL Process

### Primary Dataset Cleaning

The raw CSV required significant work before it was usable:

- **Numeric code decoding** — Class, rarity, and race were stored as integers mapped to Hearthstone's internal enums. These were decoded against verified mappings cross-referenced against known card names through the hearthstone wiki. (e.g. CLASS 12 = NEUTRAL, RARITY 1 = FREE)
- **String-formatted numbers** — Win rate fields came as `"27.80%"` and play counts as `"20,000"`. Percent signs and commas were stripped before numeric casting
- **Dash null values** — Missing values stored as `"-"` rather than null. Handled via `na_values=["-"]` at read time so they never reached the database
- **Keyword normalization** — 25 sparse boolean keyword columns (RUSH, DIVINE_SHIELD, LIFESTEAL, etc.) were normalized into a separate `minion_keyword` join table rather than kept as 25 mostly-empty columns on the main table
- **Duplicate handling** — Keyword inserts use `ON CONFLICT DO NOTHING` so re-running the pipeline doesn't create duplicate rows

**Columns dropped:** 111 of 131 columns removed, including all sparse keyword booleans (replaced by join table), non-collectible card flags, and internal Hearthstone metadata not relevant to the analysis.

### Supplementary Dataset Cleaning

- **Column selection at read time** — Only 6 of 14 columns loaded via `usecols` (Class, Expansion, DeckType, DeckArchetype, Rating, LastUpdated). Cards, CardQuantities, CardCosts, DeckCode, Title, Creator, and Link were discarded entirely
- **Ranked filter** — Filtered to `DeckType == "Ranked Deck"` only, removing Theorycraft, Wild, and casual submissions
- **Unknown archetypes removed** — `"Unknown"` archetypes made up ~43% of labeled rows and were dropped to prevent skewing archetype analysis
- **Class name standardization** — Class values uppercased (`"warlock"` → `"WARLOCK"`) to match primary dataset convention
- **Replace on load** — `if_exists="replace"` prevents duplicate accumulation on re-runs

---

## Database Schema

Three-table PostgreSQL schema under the `hearthstone` schema:

```sql
-- One row per collectible minion card
minion (
    minion_id serial primary key,
    card_name text not null,
    class text,
    rarity text,
    race text,
    cost smallint,
    attack smallint,
    health smallint,
    collectible boolean,
    elite boolean,
    mini_set boolean,
    has_battlecry boolean,
    has_deathrattle boolean,
    has_taunt boolean,
    has_discover boolean,
    has_aura boolean,
    in_perc_of_decks numeric(5,2),
    avg_copies numeric(4,2),
    deck_winrate numeric(5,2),
    times_played integer
)

-- Many-to-many: minion keywords
minion_keyword (
    minion_keyword_id serial primary key,
    minion_id int references minion(minion_id),
    keyword text,
    unique (minion_id, keyword)
)

-- Historical ranked deck submissions
deck (
    deck_id serial primary key,
    class text,
    expansion text,
    deck_archetype text,
    rating integer,
    last_updated date
)
```

---

## Pipeline Orchestration

The ETL pipeline is orchestrated by an **Apache Airflow DAG** running in Docker with four tasks in sequence:

```
extract → load_minions → load_keywords → load_decks
```

The DAG uses `schedule="@once"` since this is a historical load, not a recurring pipeline. Task dependencies enforce that minions are loaded before keywords (keywords need the minion IDs to build the lookup), and decks load independently at the end.

**Dataflow:**
```
hearthstone_minions.csv  ─┐
                          ├─► pandas (clean & transform) ─► PostgreSQL ─► Dash/Plotly
deck_data.csv            ─┘
```

---

## Technologies Used

| Tool | Purpose |
|---|---|
| Python 3 | ETL scripting |
| pandas | Data cleaning and transformation |
| SQLAlchemy | Database connection and ORM |
| psycopg | PostgreSQL driver |
| PostgreSQL | Relational data storage |
| Apache Airflow | Pipeline orchestration |
| Docker | Airflow containerization |
| Dynaconf | Environment config management via `.env` |
| Dash | Interactive dashboard framework |
| Plotly | Chart rendering |
| GitHub | Version control and project deliverables |

---

## Conclusions

**The hypothesis held up on both counts.**

Mana cost has a correlation of essentially **r ≈ 0.006** against deck win rate — there is no meaningful relationship between how much a card costs and how competitive it is. Expensive cards are not inherently stronger, cheap cards are not inherently weaker.

Keyword mechanics do show a real signal. The top-performing keywords carry average deck win rates meaningfully above the dataset average, supporting the idea that what a card does matters more than what it costs.

At the class level, win rates vary noticeably across classes in the 2024 snapshot, suggesting the meta rewards certain archetypes over others independent of individual card cost. Historically (2013–2022), class dominance shifted significantly across expansions — no single class dominated all 8 years.

**Answers to the seven questions:**

1. **Does mana cost predict win rate?** No — correlation r ≈ 0.006, essentially zero.
2. **Which keyword performs best?** DREDGE at 56.6% average win rate.
3. **Which tribes perform best?** Totems, Pirates and Murlocs seem to perform the best.
4. **Do popular minions win more?** Weakly. Most cards cluster near the average regardless of how often they're played. A few outliers are both popular and winning.
5. **Which class has the highest win rate?** PALADIN in the 2024 meta.
6. **How has class popularity changed historically?** The popularity of classes changes patch to patch but overall it appears hunter seems to be the most popular class historically as rated by the community.
7. **Which archetypes dominated historically?** Long-lived archetypes like Midrange Hunter and Control Warrior appeared across multiple expansions — see Historical Meta tab.

**Limitations:**

- The primary dataset is a single meta snapshot — balance patches shift win rates constantly. These numbers are not permanent
- The supplementary deck data comes from Hearthpwn, a community site, skewing toward engaged players rather than the full player base
- The two datasets cannot be directly joined due to different time periods — they are used for separate analyses
- Unknown archetypes (~43% of labeled ranked decks) were removed to clean up the analysis but are not represented in the archetype charts