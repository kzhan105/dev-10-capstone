import os
from dynaconf import Dynaconf
from sqlalchemy import create_engine
from etl import ETLProcessor, Transformer, DeckETLProcessor, DeckTransformer

os.chdir(os.path.dirname(__file__))


def run():
    settings = Dynaconf(envvar_prefix="DB", load_dotenv=True)
    engine = create_engine(settings["ENGINE_URL"], echo=False)

    transformer = Transformer()
    processor = ETLProcessor(engine, "hearthstone_minions.csv", transformer)
    processor.process()

    deck_transformer = DeckTransformer()
    deck_processor = DeckETLProcessor(engine, "deck_data.csv", deck_transformer)
    deck_processor.process()


if __name__ == "__main__":
    run()
