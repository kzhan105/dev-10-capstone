drop schema if exists hearthstone cascade;
create schema hearthstone;
set search_path to hearthstone;

create table minion (
    minion_id serial primary key,
    card_name text not null,
    url text,
    class text,
    rarity text,
    race text,
    cost smallint,
    attack smallint,
    health smallint,
    collectible boolean not null default true,
    elite boolean not null default false,
    mini_set boolean not null default false,
    has_battlecry boolean not null default false,
    has_deathrattle boolean not null default false,
    has_taunt boolean not null default false,
    has_discover boolean not null default false,
    has_aura boolean not null default false,
    in_perc_of_decks numeric(5,2),
    avg_copies numeric(4,2),
    deck_winrate numeric(5,2),
    times_played integer
);

create table minion_keyword (
    minion_keyword_id serial primary key,
    minion_id int not null references minion(minion_id),
    keyword text not null,
    unique (minion_id, keyword)
);

create table deck (
    deck_id serial primary key,
    class text,
    expansion text,
    deck_archetype text,
    rating integer,
    last_updated date
);