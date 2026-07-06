import os

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dash_table, dcc, html
from dynaconf import Dynaconf
from sqlalchemy import create_engine

os.chdir(os.path.dirname(__file__))

settings = Dynaconf(envvar_prefix="DB", load_dotenv=True)
engine = create_engine(settings["ENGINE_URL"])

sql = """
select
    m.minion_id,
    m.card_name,
    m.class,
    m.rarity,
    m.race,
    m.cost,
    m.attack,
    m.health,
    m.in_perc_of_decks,
    m.avg_copies,
    m.deck_winrate,
    m.times_played
from hearthstone.minion m
where m.collectible = true
"""

df = pd.read_sql(sql, engine)

numeric_columns = [
    "cost",
    "attack",
    "health",
    "in_perc_of_decks",
    "avg_copies",
    "deck_winrate",
    "times_played",
]
for column in numeric_columns:
    df[column] = pd.to_numeric(df[column], errors="coerce")

keywords_sql = """
select minion_id, keyword
from hearthstone.minion_keyword
"""
keywords_df = pd.read_sql(keywords_sql, engine)

deck_sql = """
select class, expansion, deck_archetype, rating, last_updated
from hearthstone.deck
"""
deck_df = pd.read_sql(deck_sql, engine)
deck_df["last_updated"] = pd.to_datetime(deck_df["last_updated"])
deck_df["year"] = deck_df["last_updated"].dt.year
deck_df["rating"] = pd.to_numeric(deck_df["rating"], errors="coerce")
deck_df = deck_df[deck_df["deck_archetype"] != "Unknown"]
deck_df = deck_df.dropna(subset=["deck_archetype"])

available_classes = sorted(df["class"].dropna().unique())
class_popularity = (
    df.groupby("class")["times_played"].sum().sort_values(ascending=False)
)
base_classes = class_popularity.head(5).index.tolist()

overall_avg_winrate = df["deck_winrate"].mean()
top_class = (
    df.groupby("class")["deck_winrate"].mean().sort_values(ascending=False).index[0]
)
cost_winrate_corr = df[["cost", "deck_winrate"]].corr().iloc[0, 1]

keyword_winrate_full = (
    keywords_df.merge(df[["minion_id", "deck_winrate"]], on="minion_id", how="left")
    .dropna(subset=["deck_winrate"])
    .groupby("keyword")["deck_winrate"]
    .mean()
    .sort_values(ascending=False)
)
top_keyword = keyword_winrate_full.index[0]
top_keyword_wr = keyword_winrate_full.iloc[0]

keyword_summary_full = (
    keyword_winrate_full.reset_index()
    .rename(columns={"deck_winrate": "avg_winrate"})
    .head(10)
)
keyword_summary_full["vs_average"] = (
    keyword_summary_full["avg_winrate"] - overall_avg_winrate
)

conclusion_keyword_fig = px.bar(
    keyword_summary_full,
    x="keyword",
    y="vs_average",
    color="vs_average",
    color_continuous_scale="RdYlGn",
    title="Keyword Win Rate Relative to Dataset Average",
    labels={"vs_average": "Win Rate vs Average (pp)", "keyword": "Keyword"},
)
conclusion_keyword_fig.add_hline(y=0, line_dash="dash", line_color="gray")
conclusion_keyword_fig.update_layout(coloraxis_showscale=False)

class_over_time = (
    deck_df.groupby(["year", "class"]).size().reset_index(name="deck_count")
)
top_historical_classes = (
    deck_df.groupby("class").size().sort_values(ascending=False).head(6).index.tolist()
)
class_over_time_filtered = class_over_time[
    class_over_time["class"].isin(top_historical_classes)
]

class_over_time_fig = px.line(
    class_over_time_filtered,
    x="year",
    y="deck_count",
    color="class",
    title="Ranked Deck Count by Class Over Time (2013–2022)",
    labels={"deck_count": "Number of Decks", "year": "Year", "class": "Class"},
)

avg_rating_by_class = (
    deck_df.groupby("class")["rating"]
    .mean()
    .reset_index()
    .rename(columns={"rating": "avg_rating"})
    .sort_values("avg_rating", ascending=False)
    .head(12)
)

avg_rating_fig = px.bar(
    avg_rating_by_class,
    x="class",
    y="avg_rating",
    color="avg_rating",
    color_continuous_scale="Blues",
    title="Average Deck Rating by Class (Historical)",
    labels={"avg_rating": "Avg Rating", "class": "Class"},
)
avg_rating_fig.update_layout(coloraxis_showscale=False, showlegend=False)

top_archetypes = (
    deck_df.groupby("deck_archetype")
    .size()
    .reset_index(name="count")
    .dropna()
    .sort_values("count", ascending=False)
    .head(10)
)

archetype_fig = px.bar(
    top_archetypes,
    x="count",
    y="deck_archetype",
    orientation="h",
    title="Top 10 Most Popular Deck Archetypes (Historical)",
    labels={"count": "Number of Decks", "deck_archetype": "Archetype"},
)
archetype_fig.update_layout(yaxis={"categoryorder": "total ascending"})

app = Dash(__name__)

CARD_STYLE = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "10px",
    "padding": "20px",
    "marginBottom": "20px",
    "boxShadow": "0 1px 3px rgba(0,0,0,0.1)",
}

STAT_BOX_STYLE = {
    "textAlign": "center",
    "padding": "20px",
    "backgroundColor": "white",
    "borderRadius": "10px",
    "boxShadow": "0 1px 3px rgba(0,0,0,0.1)",
    "flex": "1",
    "margin": "0 10px",
}


def stat_box(label, value):
    return html.Div(
        [
            html.H3(value, style={"margin": "0", "color": "#1f3a5f"}),
            html.P(label, style={"margin": "0", "color": "#666"}),
        ],
        style=STAT_BOX_STYLE,
    )


CAPTION_STYLE = {
    "fontSize": "14px",
    "color": "#555",
    "marginTop": "0px",
    "marginBottom": "20px",
    "padding": "0 10px",
    "lineHeight": "1.5",
}


def caption(text):
    return html.P(text, style=CAPTION_STYLE)


intro_tab = html.Div(
    [
        html.H2("Hearthstone Minions: Capstone Project"),
        html.P(
            "Hearthstone is a digital collectible card game by Blizzard Entertainment. Players build decks of 30 cards and "
            "battle each other online. With over 3,000 collectible minion cards in the game, "
            "each one has a mana cost, attack, health, a class it belongs to, a race or tribe, "
            "and sometimes a keyword ability like Rush, Divine Shield, or Reborn. " 
        ),
        html.H3("Hypothesis"),
        html.P(
            "Minions with strong keyword synergies (Rush, Divine Shield, Reborn, etc.) and specific tribal synergies (Murlocs, Pirates, Totems, etc.) "
            "outperform the field in average deck win rate — and raw mana cost alone has "
            "little to no relationship with how competitive a card actually is. "
            "In other words: expensive cards aren't inherently better, and cheap ones aren't inherently worse."
        ),
        html.H3("Questions"),
        html.Ul(
            [
                html.Li(
                    "Does a minion's mana cost correlate with its competitive win rate?"
                ),
                html.Li(
                    "Which keyword mechanics appear most in high-performing decks?"
                ),
                html.Li(
                    "Which minion races (tribes) see the strongest competitive performance?"
                ),
                html.Li(
                    "Are the most-played minions also the highest win-rate minions, or do popularity and performance diverge?"
                ),
                html.Li("Which class has the highest average deck win rate?"),
                html.Li(
                    "How has class popularity in ranked decks changed over 8 years of Hearthstone history?"
                ),
                html.Li("Which deck archetypes were most dominant historically?"),
            ]
        ),
        html.H3("Datasets"),
        html.P("Two datasets were used for this project:"),
        html.Ul(
            [
                html.Li(
                    [
                        html.B("Primary: "),
                        "3,025 collectible Hearthstone minion cards with 131 attributes — card stats, "
                        "class/race/rarity encodings, 25 keyword boolean flags, and competitive performance "
                        "metrics from HSReplay. Reflects the early 2024 meta. ",
                        html.Br(),
                        html.I(
                            "samfo1. (2024). Hearthstone minions stats and popularity [Dataset]. Kaggle. "
                            "https://www.kaggle.com/datasets/samfo1/hearthstone-minions-stats-and-popularity. Accessed June 2026."
                        ),
                    ]
                ),
                html.Li(
                    [
                        html.B("Supplementary: "),
                        f"{len(deck_df):,} ranked Hearthstone decks submitted to Hearthpwn from 2013–2022, "
                        "filtered down from 668k+ total decks. Gives us the historical class and archetype picture. ",
                        html.Br(),
                        html.I(
                            "Crowder, S. (2022). 8 Years of Hearthstone Decks [Dataset]. Kaggle. "
                            "https://www.kaggle.com/datasets/sarahcrowder/8-years-of-hearthstone-decks. Accessed June 2026."
                        ),
                    ]
                ),
            ]
        ),
        html.Div(
            [
                stat_box("Minions Analyzed", f"{len(df):,}"),
                stat_box("Avg Deck Win Rate", f"{overall_avg_winrate:.1f}%"),
                stat_box("Top Performing Class", str(top_class)),
                stat_box("Top Keyword", f"{top_keyword} ({top_keyword_wr:.1f}%)"),
                stat_box("Historical Ranked Decks", f"{len(deck_df):,}"),
            ],
            style={"display": "flex", "marginTop": "30px"},
        ),
    ],
    style=CARD_STYLE,
)

methodology_tab = html.Div(
    [
        html.H2("Methodology"),
        html.P(
            "Here's how the data went from two messy CSVs on Kaggle to what you're looking at now."
        ),
        html.H3("The Raw Data"),
        html.P(
            "The primary dataset came in as a single CSV with 3,025 rows and 131 columns. "
            "That sounds like an insane amount of data but most of those 131 columns were nearly empty. "
            "Class, rarity, and race weren't stored as readable strings either; "
            "they were numeric codes that had to be decoded by cross-referencing Hearthstone's "
            "wiki pages against known card names. "
            "Win rate and deck percentage came in as strings like '27.80%', play counts had commas "
            "like '20,000', and missing values were stored as a literal dash '-' instead of null."
        ),
        html.P(
            "The supplementary dataset was 668k+ rows of deck submissions going from 2022 all the way back to 2013. "
            "It had everything — deck titles, full card lists, card costs, creators, deck codes — "
            "most of which we didn't need. It also had a lot of noise: decks with no archetype label, "
            "casual and wild format decks, and nearly half the rows tagged 'Unknown' for archetype."
        ),
        html.H3("What Got Cut"),
        html.Ul(
            [
                html.Li(
                    "Primary: 111 of 131 columns dropped — including 25 sparse keyword boolean flags that were normalized into a join table instead."
                ),
                html.Li(
                    "Primary: Non-collectible cards filtered out — tokens, hero cards, and uncollectible effects aren't cards players can put in decks."
                ),
                html.Li(
                    "Supplementary: Cards, CardQuantities, CardCosts, DeckCode, Title, Creator, and Link columns all dropped as we only needed class, expansion, archetype, rating, and date."
                ),
                html.Li(
                    f"Supplementary: Filtered from 668k+ rows to {len(deck_df):,} by keeping only Ranked Decks and removing Unknown archetypes (~43% of labeled rows)."
                ),
            ]
        ),
        html.H3("ETL — Primary Dataset"),
        html.Ul(
            [
                html.Li(
                    "Class, rarity, and race numeric codes decoded against Hearthstone's internal enum mappings and verified by checking known cards through the wiki."
                ),
                html.Li(
                    "'27.80%' → 27.80 and '20,000' → 20000 via string stripping before numeric cast."
                ),
                html.Li(
                    "Dash '-' values treated as NaN at read time so they never reached the database."
                ),
                html.Li(
                    "25 sparse keyword columns normalized into a minion_keyword join table — one row per card per keyword instead of 25 mostly-empty columns on minion."
                ),
            ]
        ),
        html.H3("ETL — Supplementary Dataset"),
        html.Ul(
            [
                html.Li(
                    "usecols at read time — only 6 of 14 columns loaded into memory, keeping it efficient on a 668k row file."
                ),
                html.Li(
                    "Filtered to DeckType = 'Ranked Deck' — cuts out Theorycraft, Wild, and casual submissions."
                ),
                html.Li(
                    "'Unknown' archetypes dropped — noise with no analytical value."
                ),
                html.Li(
                    "Class names uppercased ('warlock' → 'WARLOCK') to match primary dataset convention."
                ),
                html.Li(
                    "if_exists='replace' on load so the deck table is always clean on re-run, no duplicate accumulation."
                ),
            ]
        ),
        html.H3("Dataflow"),
        html.P(
            "CSV → pandas (clean & transform) → Airflow DAG → PostgreSQL (hearthstone schema) → Dash/Plotly"
        ),
        html.H3("Database Schema"),
        html.P("Three tables in PostgreSQL under the hearthstone schema:"),
        html.Ul(
            [
                html.Li(
                    "minion — 3,025 rows, one per collectible card, 20 cleaned columns."
                ),
                html.Li(
                    "minion_keyword — many-to-many join table linking minions to their active keyword mechanics."
                ),
                html.Li(
                    f"deck — {len(deck_df):,} rows of ranked historical decks from 2013–2022."
                ),
            ]
        ),
        html.P(
            "Orchestrated by an Apache Airflow DAG running in Docker: extract → load_minions → load_keywords → load_decks."
        ),
        html.H3("Tools"),
        html.Ul(
            [
                html.Li("Python (pandas, SQLAlchemy, psycopg) — ETL and cleaning"),
                html.Li("PostgreSQL — relational storage"),
                html.Li("Apache Airflow (Docker) — pipeline orchestration"),
                html.Li("Dynaconf — environment config via .env"),
                html.Li("Dash / Plotly — this dashboard"),
                html.Li("GitHub — version control"),
            ]
        ),
    ],
    style=CARD_STYLE,
)

findings_tab = html.Div(
    [
        html.H2("Findings — 2024 Meta"),
        html.P(
            "All charts below are based on the primary dataset — 3,025 collectible minions "
            "with competitive performance data from early 2024. Use the class filter to narrow "
            "down the view. It defaults to the top 5 most-played classes by total times played."
        ),
        html.Label("Filter by Class", style={"fontWeight": "bold"}),
        dcc.Dropdown(
            id="class_dropdown",
            options=[{"label": c, "value": c} for c in available_classes],
            value=base_classes,
            multi=True,
        ),
        html.Br(),
        html.Div(
            [
                html.Div(
                    [
                        dcc.Graph(id="winrate_by_class_chart"),
                        caption(
                            "Each box shows the spread of deck win rates for minions "
                            "in that class. Higher, tighter boxes mean more consistently "
                            "strong performance — useful for spotting which classes are "
                            "currently favored in the meta."
                        ),
                    ],
                    style={"flex": "1"},
                ),
                html.Div(
                    [
                        dcc.Graph(id="winrate_by_race_chart"),
                        caption(
                            "Same idea, but grouped by minion race (tribe). "
                            "Tribes sorted left to right by median win rate — "
                            "a quick read on which tribal synergies are paying off."
                        ),
                    ],
                    style={"flex": "1"},
                ),
            ],
            style={"display": "flex", "gap": "20px"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        dcc.Graph(id="cost_vs_winrate_chart"),
                        caption(
                            "Each point is a minion. If cost mattered for win rate "
                            "we'd expect a clear trend — instead the points are "
                            "scattered with no pattern, supporting the hypothesis "
                            "that cost alone doesn't predict performance."
                        ),
                    ],
                    style={"flex": "1"},
                ),
                html.Div(
                    [
                        dcc.Graph(id="keyword_winrate_chart"),
                        caption(
                            "Average deck win rate for minions carrying each keyword. "
                            "The n= label shows how many minions have that keyword — "
                            "useful context since smaller samples are noisier."
                        ),
                    ],
                    style={"flex": "1"},
                ),
            ],
            style={"display": "flex", "gap": "20px"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        dcc.Graph(id="popularity_vs_winrate_chart"),
                        caption(
                            "X-axis is how often a minion was played, Y-axis is its "
                            "win rate, and bubble size is the percent of decks it "
                            "appears in. The dashed line marks the dataset average — "
                            "points above it and to the right are the strongest cards "
                            "in the current meta."
                        ),
                    ],
                    style={"flex": "1"},
                ),
            ],
            style={"display": "flex", "gap": "20px"},
        ),
    ],
    style=CARD_STYLE,
)

historical_tab = html.Div(
    [
        html.H2("Historical Meta (2013\u20132022)"),
        html.P(
            f"This tab pulls from the supplementary dataset \u2014 {len(deck_df):,} ranked decks "
            "submitted to Hearthpwn between 2013 and 2022. Since this data predates the 2024 "
            "snapshot in the primary dataset, we can't directly compare win rates. What we can do "
            "is look at how class popularity and deck archetypes shifted over 8 years of expansions, "
            "patches, and meta shakeups \u2014 and see whether the classes dominating historically "
            "are the same ones leading the 2024 win rate charts."
        ),
        html.Div(
            [
                html.Div(
                    [
                        dcc.Graph(
                            id="class_over_time_chart", figure=class_over_time_fig
                        ),
                        caption(
                            "Ranked deck submissions by class over 8 years. Peaks and valleys "
                            "reflect expansion releases, balance patches, and shifting metas — "
                            "classes that spike often received powerful new cards that expansion."
                        ),
                    ],
                    style={"flex": "1"},
                ),
                html.Div(
                    [
                        dcc.Graph(id="avg_rating_chart", figure=avg_rating_fig),
                        caption(
                            "Average community rating of ranked decks by class. Higher ratings "
                            "suggest the community considered that class's decks stronger or "
                            "more refined over the 8-year period."
                        ),
                    ],
                    style={"flex": "1"},
                ),
            ],
            style={"display": "flex", "gap": "20px"},
        ),
        dcc.Graph(id="archetype_chart", figure=archetype_fig),
        caption(
            "The 10 most submitted ranked deck archetypes across all 8 years. "
            "Archetypes like Midrange Hunter and Control Warrior dominated multiple "
            "expansions, reflecting their long-term viability in the competitive meta."
        ),
    ],
    style=CARD_STYLE,
)

conclusion_tab = html.Div(
    [
        html.H2("Conclusion"),
        html.P(
            f"Mana cost shows almost no correlation with deck win rate "
            f"(r = {cost_winrate_corr:.3f}), meaning cheap minions are not "
            f"inherently weaker, and expensive minions are not inherently "
            f"stronger — supporting the second half of the hypothesis."
        ),
        html.P(
            f"Keyword mechanics do correlate with stronger performance: minions "
            f"with {top_keyword} carry the highest average deck win rate at "
            f"{top_keyword_wr:.1f}%, ahead of the {overall_avg_winrate:.1f}% "
            f"dataset average — supporting the first half of the hypothesis."
        ),
        html.P(
            f"At the class level, {top_class} minions post the highest average "
            f"win rate in the 2024 snapshot. Historically, class dominance shifted "
            f"significantly across expansions — no single class dominated all 8 years."
        ),
        html.H3("Win Rate by Keyword vs Dataset Average"),
        dcc.Graph(id="conclusion_keyword_chart", figure=conclusion_keyword_fig),
        caption(
            "Green bars beat the dataset average win rate, red bars fall below it. "
            "This is the clearest visual evidence for the keyword half of the hypothesis."
        ),
        html.H3("Answers to Key Questions"),
        html.Ul(
            [
                html.Li(
                    f"Does mana cost predict win rate? → No. Correlation r = {cost_winrate_corr:.3f}, essentially zero."
                ),
                html.Li(
                    f"Which keyword performs best? → {top_keyword} at {top_keyword_wr:.1f}% average win rate."
                ),
                html.Li(
                    "Which races perform best? → Totems, Pirates and Murlocs seem to perform the best. (which is interesting as it seems in the past decks dragon priest and beast hunter performed the best.)"
                ),
                html.Li(
                    "Do popular minions win more? → Weakly. Most cluster near average; a few outliers exist above the line."
                ),
                html.Li(
                    f"Which class has the highest win rate? → {top_class} in the 2024 meta."
                ),
                html.Li(
                    "How has class popularity changed historically? → The popularity of classes changes patch to patch but overall it appears hunter seems to be the most popular class historically as rated by the community."
                ),
                html.Li(
                    "Which archetypes dominated historically? → The most popular archetypes historically have been Midrange hunter and Control warrior."
                ),
            ]
        ),
        html.H3("Limitations"),
        html.P("A few honest caveats worth flagging:"),
        html.Ul(
            [
                html.Li(
                    "The primary dataset is a single meta snapshot — Hearthstone gets balance patches regularly, so a card that was dominant in early 2024 might have been nerfed since. The numbers here are not permanent truths."
                ),
                html.Li(
                    "The supplementary deck data comes from Hearthpwn, a community deckbuilding site — it skews toward engaged players who bother to post decks, not the average player base."
                ),
                html.Li(
                    "The two datasets cover different time periods (2013–2022 vs. early 2024) so they can't be directly joined — they're used for separate analyses."
                ),
                html.Li(
                    "Unknown archetypes were removed from the supplementary dataset, but they made up ~43% of labeled decks — so the archetype charts represent the named meta, not all ranked play."
                ),
            ]
        ),
        html.H3("Dataset Preview"),
        dash_table.DataTable(
            data=df.head(500).to_dict("records"),
            columns=[{"name": i, "id": i} for i in df.columns],
            page_size=10,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
        ),
    ],
    style=CARD_STYLE,
)

app.layout = html.Div(
    [
        html.H1("Hearthstone Minions Dashboard", style={"textAlign": "center"}),
        dcc.Tabs(
            id="tabs",
            value="intro",
            children=[
                dcc.Tab(label="Introduction", value="intro", children=[intro_tab]),
                dcc.Tab(
                    label="Methodology", value="methodology", children=[methodology_tab]
                ),
                dcc.Tab(label="Findings", value="findings", children=[findings_tab]),
                dcc.Tab(
                    label="Historical Meta",
                    value="historical",
                    children=[historical_tab],
                ),
                dcc.Tab(
                    label="Conclusion", value="conclusion", children=[conclusion_tab]
                ),
            ],
        ),
    ],
    style={
        "padding": "20px",
        "fontFamily": "Arial",
        "maxWidth": "1200px",
        "margin": "0 auto",
    },
)


@callback(
    Output("winrate_by_class_chart", "figure"),
    Output("winrate_by_race_chart", "figure"),
    Output("cost_vs_winrate_chart", "figure"),
    Output("keyword_winrate_chart", "figure"),
    Output("popularity_vs_winrate_chart", "figure"),
    Input("class_dropdown", "value"),
)
def update_graphs(selected_classes):
    filtered_df = df[df["class"].isin(selected_classes)]

    winrate_by_class_fig = px.box(
        filtered_df.dropna(subset=["deck_winrate"]),
        x="class",
        y="deck_winrate",
        color="class",
        title="Deck Win Rate by Class",
        labels={"deck_winrate": "Deck Win Rate (%)", "class": "Class"},
    )
    winrate_by_class_fig.update_layout(showlegend=False)

    winrate_by_race_fig = px.box(
        filtered_df.dropna(subset=["deck_winrate", "race"]),
        x="race",
        y="deck_winrate",
        color="race",
        title="Deck Win Rate by Minion Race (Tribal Synergy)",
        labels={"deck_winrate": "Deck Win Rate (%)", "race": "Race"},
    )
    winrate_by_race_fig.update_layout(showlegend=False)
    winrate_by_race_fig.update_xaxes(categoryorder="median descending")

    cost_winrate_fig = px.scatter(
        filtered_df.dropna(subset=["deck_winrate", "cost"]),
        x="cost",
        y="deck_winrate",
        color="class",
        hover_data=["card_name"],
        title="Cost vs Deck Win Rate",
        labels={"cost": "Mana Cost", "deck_winrate": "Deck Win Rate (%)"},
    )

    filtered_minion_ids = filtered_df["minion_id"]
    filtered_keywords = keywords_df[keywords_df["minion_id"].isin(filtered_minion_ids)]
    keyword_merged = filtered_keywords.merge(
        df[["minion_id", "deck_winrate"]], on="minion_id", how="left"
    ).dropna(subset=["deck_winrate"])

    keyword_summary = (
        keyword_merged.groupby("keyword")
        .agg(avg_winrate=("deck_winrate", "mean"), count=("minion_id", "count"))
        .reset_index()
        .sort_values("avg_winrate", ascending=False)
        .head(10)
    )

    keyword_winrate_fig = px.bar(
        keyword_summary,
        x="avg_winrate",
        y="keyword",
        orientation="h",
        text="count",
        title="Top 10 Keywords by Average Deck Win Rate",
        labels={"avg_winrate": "Avg Deck Win Rate (%)", "keyword": "Keyword"},
    )
    keyword_winrate_fig.update_traces(texttemplate="n=%{text}", textposition="outside")
    keyword_winrate_fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis={"range": [0, keyword_summary["avg_winrate"].max() * 1.25]},
    )

    top_played = filtered_df.dropna(subset=["times_played", "deck_winrate"]).nlargest(
        3, "times_played"
    )

    popularity_vs_winrate_fig = px.scatter(
        filtered_df.dropna(subset=["times_played", "deck_winrate"]),
        x="times_played",
        y="deck_winrate",
        color="class",
        size="in_perc_of_decks",
        hover_data=["card_name"],
        title="Popularity (Times Played) vs Deck Win Rate",
        labels={"times_played": "Times Played", "deck_winrate": "Deck Win Rate (%)"},
    )
    popularity_vs_winrate_fig.add_hline(
        y=overall_avg_winrate,
        line_dash="dash",
        line_color="gray",
        annotation_text="Dataset Avg Win Rate",
    )
    for _, row in top_played.iterrows():
        popularity_vs_winrate_fig.add_annotation(
            x=row["times_played"],
            y=row["deck_winrate"],
            text=row["card_name"],
            showarrow=True,
            arrowhead=1,
            yshift=10,
        )

    return (
        winrate_by_class_fig,
        winrate_by_race_fig,
        cost_winrate_fig,
        keyword_winrate_fig,
        popularity_vs_winrate_fig,
    )


if __name__ == "__main__":
    app.run(debug=True)
