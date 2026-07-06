from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime

from etl import ETLProcessor, Transformer, DeckETLProcessor, DeckTransformer

MINION_CSV_PATH = "/opt/airflow/dags/hearthstone_minions.csv"
DECK_CSV_PATH = "/opt/airflow/dags/deck_data.csv"


def get_engine():
    return PostgresHook(postgres_conn_id="hearthstone_conn").get_sqlalchemy_engine()


def get_processor():
    return ETLProcessor(get_engine(), MINION_CSV_PATH, Transformer())


def get_deck_processor():
    return DeckETLProcessor(get_engine(), DECK_CSV_PATH, DeckTransformer())


@dag(
    start_date=datetime(2026, 6, 1),
    schedule="@once",
    catchup=False,
    tags=["hearthstone", "etl"],
)
def hearthstone_etl():

    @task
    def load_minions():
        processor = get_processor()
        raw_df = processor.extract()
        minion_df = processor._transformer.transform_minions(raw_df)
        processor.load_minions(minion_df)
        print(f"Loaded {len(minion_df)} minions.")

    @task
    def load_keywords():
        processor = get_processor()
        raw_df = processor.extract()
        minion_lookup = processor.build_minion_lookup()
        keyword_df = processor._transformer.transform_keywords(raw_df, minion_lookup)
        processor.load_keywords(keyword_df)
        print(f"Loaded {len(keyword_df)} keyword records.")

    @task
    def load_decks():
        processor = get_deck_processor()
        raw_df = processor.extract()
        deck_df = processor._transformer.transform_decks(raw_df)
        processor.load_decks(deck_df)
        print(f"Loaded {len(deck_df)} deck records.")

    load_minions() >> load_keywords() >> load_decks()


dag = hearthstone_etl()
