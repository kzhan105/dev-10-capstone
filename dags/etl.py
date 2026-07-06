import pandas as pd

CLASS_MAP = {
    1: "DEATH_KNIGHT",
    2: "DRUID",
    3: "HUNTER",
    4: "MAGE",
    5: "PALADIN",
    6: "PRIEST",
    7: "ROGUE",
    8: "SHAMAN",
    9: "WARLOCK",
    10: "WARRIOR",
    12: "NEUTRAL",
    14: "DEMON_HUNTER",
}

RARITY_MAP = {
    1: "FREE",
    2: "COMMON",
    3: "RARE",
    4: "EPIC",
    5: "LEGENDARY",
}

RACE_MAP = {
    11: "UNDEAD",
    14: "MURLOC",
    15: "DEMON",
    17: "MECH",
    18: "ELEMENTAL",
    20: "BEAST",
    21: "TOTEM",
    23: "PIRATE",
    24: "DRAGON",
    26: "AMALGAM",
    43: "QUILBOAR",
    92: "NAGA",
}

KEYWORDS = [
    "RUSH",
    "DIVINE_SHIELD",
    "LIFESTEAL",
    "POISONOUS",
    "WINDFURY",
    "MEGA_WINDFURY",
    "CHARGE",
    "STEALTH",
    "REBORN",
    "FREEZE",
    "SILENCE",
    "MAGNETIC",
    "ECHO",
    "TRADEABLE",
    "COLOSSAL",
    "INFUSE",
    "FORGE",
    "DREDGE",
    "CORRUPT",
    "SPELLBURST",
    "FRENZY",
    "OVERKILL",
    "OUTCAST",
    "HONORABLEKILL",
    "OVERHEAL",
]


class Transformer:
    def clean_percent(self, val):
        if pd.isna(val):
            return None
        return float(str(val).replace("%", "").strip())

    def clean_int(self, val):
        if pd.isna(val):
            return None
        return int(str(val).replace(",", "").strip())

    def flag(self, val):
        return pd.notna(val) and val == 1.0

    def transform_minions(self, df):
        records = []
        for _, row in df.iterrows():
            records.append(
                {
                    "card_name": row["card_name"],
                    "url": row.get("url"),
                    "class": CLASS_MAP.get(row["CLASS"])
                    if pd.notna(row.get("CLASS"))
                    else None,
                    "rarity": RARITY_MAP.get(row["RARITY"])
                    if pd.notna(row.get("RARITY"))
                    else None,
                    "race": RACE_MAP.get(row["CARDRACE"])
                    if pd.notna(row.get("CARDRACE"))
                    else None,
                    "cost": int(row["COST"]) if pd.notna(row.get("COST")) else None,
                    "attack": int(row["ATK"]) if pd.notna(row.get("ATK")) else None,
                    "health": int(row["HEALTH"])
                    if pd.notna(row.get("HEALTH"))
                    else None,
                    "collectible": self.flag(row.get("COLLECTIBLE")),
                    "elite": self.flag(row.get("ELITE")),
                    "mini_set": self.flag(row.get("MINI_SET")),
                    "has_battlecry": self.flag(row.get("BATTLECRY")),
                    "has_deathrattle": self.flag(row.get("DEATHRATTLE")),
                    "has_taunt": self.flag(row.get("TAUNT")),
                    "has_discover": self.flag(row.get("DISCOVER")),
                    "has_aura": self.flag(row.get("AURA")),
                    "in_perc_of_decks": self.clean_percent(row.get("in_perc_of_decks")),
                    "avg_copies": float(str(row["avg_copies"]).strip())
                    if pd.notna(row.get("avg_copies"))
                    else None,
                    "deck_winrate": self.clean_percent(row.get("deck_winrate")),
                    "times_played": self.clean_int(row.get("times_played")),
                }
            )
        return pd.DataFrame(records)

    def transform_keywords(self, df, minion_lookup):
        records = []
        for _, row in df.iterrows():
            minion_id = minion_lookup.get(row["card_name"])
            if minion_id is None:
                continue
            for kw in KEYWORDS:
                if self.flag(row.get(kw)):
                    records.append({"minion_id": minion_id, "keyword": kw})
        return pd.DataFrame(records)


class ETLProcessor:
    def __init__(self, cnx, file_path, transformer: Transformer):
        self._cnx = cnx
        self._file_path = file_path
        self._transformer = transformer

    def extract(self):
        return pd.read_csv(self._file_path, na_values=["", " ", "-", "NA"])

    def load_minions(self, df):
        df.to_sql(
            "minion", self._cnx, schema="hearthstone", if_exists="append", index=False
        )

    def load_keywords(self, df):
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy import Table, Column, Integer, Text, MetaData

        meta = MetaData()
        table = Table(
            "minion_keyword",
            meta,
            Column("minion_id", Integer),
            Column("keyword", Text),
            schema="hearthstone",
        )
        with self._cnx.connect() as conn:
            for _, row in df.iterrows():
                stmt = (
                    insert(table)
                    .values(minion_id=row["minion_id"], keyword=row["keyword"])
                    .on_conflict_do_nothing()
                )
                conn.execute(stmt)
            conn.commit()

    def build_minion_lookup(self):
        sql = "select minion_id, card_name from hearthstone.minion"
        df = pd.read_sql(sql, self._cnx)
        return dict(zip(df["card_name"], df["minion_id"]))

    def process(self):
        raw_df = self.extract()

        minion_df = self._transformer.transform_minions(raw_df)
        self.load_minions(minion_df)
        print("Minion table loaded.")

        minion_lookup = self.build_minion_lookup()

        keyword_df = self._transformer.transform_keywords(raw_df, minion_lookup)
        self.load_keywords(keyword_df)
        print("Minion keyword table loaded.")

        print("ETL COMPLETE.")


class DeckTransformer:
    def transform_decks(self, df):
        deck_df = df[
            ["Class", "Expansion", "DeckType", "DeckArchetype", "Rating", "LastUpdated"]
        ].copy()
        deck_df.columns = [
            "class",
            "expansion",
            "deck_type",
            "deck_archetype",
            "rating",
            "last_updated",
        ]
        deck_df["class"] = deck_df["class"].str.upper().str.strip()
        deck_df["expansion"] = deck_df["expansion"].str.strip()
        deck_df["deck_type"] = deck_df["deck_type"].str.strip()
        deck_df["deck_archetype"] = deck_df["deck_archetype"].str.strip()
        deck_df["rating"] = pd.to_numeric(deck_df["rating"], errors="coerce").astype(
            "Int64"
        )
        deck_df["last_updated"] = pd.to_datetime(
            deck_df["last_updated"], errors="coerce"
        ).dt.date
        deck_df = deck_df.dropna(subset=["class", "last_updated"])
        deck_df = deck_df[deck_df["deck_type"] == "Ranked Deck"]
        deck_df = deck_df[deck_df["deck_archetype"] != "Unknown"]
        deck_df = deck_df.dropna(subset=["deck_archetype"])
        deck_df = deck_df.drop(columns=["deck_type"])
        return deck_df


class DeckETLProcessor:
    def __init__(self, cnx, file_path, transformer: DeckTransformer):
        self._cnx = cnx
        self._file_path = file_path
        self._transformer = transformer

    def extract(self):
        df = pd.read_csv(
            self._file_path,
            usecols=[
                "Class",
                "Expansion",
                "DeckType",
                "DeckArchetype",
                "Rating",
                "LastUpdated",
            ],
            na_values=["", " ", "NA", "None"],
        )
        print(f"Extracted {len(df)} deck rows.")
        return df

    def load_decks(self, df):
        df.to_sql(
            "deck", self._cnx, schema="hearthstone", if_exists="replace", index=False
        )

    def process(self):
        raw_df = self.extract()
        deck_df = self._transformer.transform_decks(raw_df)
        self.load_decks(deck_df)
        print("Deck table loaded.")
        print("DECK ETL COMPLETE.")
