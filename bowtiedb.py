import sqlite3
import threading
import functools
import os
import logging
import time
from typing import Dict, List, Optional, Text, Union
from dataclasses import dataclass
from dataclasses_json.api import DataClassJsonMixin
from marshmallow.fields import String

from telegram.messageentity import MessageEntity

class ThreadDb(threading.local):
    con = None
    con: sqlite3.Connection
    cur = None
    cur: sqlite3.Cursor


localthreaddb = ThreadDb()

def create_connection() -> sqlite3.Connection:
    return sqlite3.connect(os.getenv("DB"))


def with_connection(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        con = create_connection()
        # Preserve old connection and cursor
        oldcon = localthreaddb.con
        oldcur = localthreaddb.cur
        # Set current connection as the thread connection
        localthreaddb.con = con
        localthreaddb.cur = None
        try:
            result = func(*args, **kwargs)
            con.commit()
            return result
        except Exception as e:
            con.rollback()
            raise
        finally:
            con.close()
            # Restore old connection and cursor
            localthreaddb.con = oldcon
            localthreaddb.cur = oldcur
    return wrapper

def with_retry(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for i in range(10):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                logging.warn("sqlite3 operational error", e)
                time.sleep(0.2)
        con = create_connection()
    return wrapper

def with_cursor(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        con = localthreaddb.con
        cur = localthreaddb.cur

        if cur:
            # Rely on the upper execution to close the cursor and handle exceptions
            return func(*args, **kwargs)
        elif con:
            cur = con.cursor()
            localthreaddb.cur = cur
            try:
                return func(*args, **kwargs)
            finally:
                # SQL in general can only have one cursor at a time.
                # Because we replaced it, it is not appropriate to restore it
                # as the cursro would not be valid
                localthreaddb.cur = None
        else:
            # Create a new connection and a new cursor
            con = create_connection()
            localthreaddb.con = con
            cur = con.cursor()
            localthreaddb.cur = con.cursor()
            try:
                result = func(*args, **kwargs)
                con.commit()
                return result
            except Exception as e:
                con.rollback()
                raise
            finally:
                cur.close()
                con.close()
                # Clear both as the connection was only used for this invocation
                localthreaddb.cur = None
                localthreaddb.con = None
    return wrapper

@dataclass
class TelegramMessageEntity(DataClassJsonMixin):
    type: str  # pylint: disable=W0622
    offset: int
    length: int
    url: Optional[Text] = None

@dataclass
class Entry(DataClassJsonMixin):
    date: int
    content: Optional[Text]
    photo: Optional[Text]
    entities: List[TelegramMessageEntity]
    display_name: Optional[Text]
    icon: Optional[Text]
    identity: Optional[int] = None

@dataclass
class Asset(DataClassJsonMixin):
    source: String
    variant: String
    destination: String
    identity: Optional[int] = None

@with_cursor
@with_retry
def find_entries(limit:int=10,offset:int=0) -> List[Entry]:
    results = localthreaddb.cur.execute("select id, date, content, photo, entities, display_name, icon from bowtie_entry order by date desc limit :limit offset :offset", {
        "limit": limit,
        "offset": offset
    }).fetchall()
    if results and len(results) > 0:
        entries = []
        for result in results:
            entities_string = result[4]
            entities = []
            if entities_string:
                entities = TelegramMessageEntity.schema(many=True).loads(entities_string)
        
            entries.append(Entry(result[1], result[2], result[3], entities, result[5], result[6], result[0]))
        # logging.info("Found %d entries", len(results))
        return entries
    return []

@with_cursor
@with_retry
def add_entry(entry: Entry) -> None:
    encoded_entities = None
    if entry.entities:
        encoded_entities = TelegramMessageEntity.schema(many=True).dumps(entry.entities)
    localthreaddb.cur.execute("insert into bowtie_entry(date, content, photo, entities, display_name, icon) values (:date, :content, :photo, :entities, :display_name, :icon)", {
        "date": entry.date,
        "content": entry.content,
        "photo": entry.photo,
        "entities": encoded_entities,
        "display_name": entry.display_name,
        "icon": entry.icon
    })
        

@with_cursor
@with_retry
def add_asset(asset: Asset) -> None:
    localthreaddb.cur.execute("insert into bowtie_asset(source, variant, destination) values (:source, :variant, :destination)", {
        "source": asset.source,
        "variant": asset.variant,
        "destination": asset.destination
    })

@with_cursor
@with_retry
def find_asset(source: String, variant: String) -> Optional[Asset]:
    results = localthreaddb.cur.execute("select id, source, variant, destination from bowtie_asset where source = :source and variant = :variant", {
        "source": source,
        "variant": variant
    }).fetchone()
    if results and len(results) > 0:
        return Asset(results[1], results[2], results[3], results[0])
    return None

@with_connection
@with_cursor
@with_retry
def has_tweet(identity: int) -> bool:
    results = localthreaddb.cur.execute("select id from bowtie_tweet where id = :id", {
        "id": identity
    }).fetchone()
    if results and len(results) > 0:
        return True
    return False

@with_cursor
@with_retry
def has_tweet(identity: int) -> bool:
    results = localthreaddb.cur.execute("select id from bowtie_tweet where id = :id", {
        "id": identity
    }).fetchone()
    if results and len(results) > 0:
        return True
    return False

@with_cursor
@with_retry
def save_tweet(identity: int, json: Text) -> None:
    localthreaddb.cur.execute("insert into bowtie_tweet(id, json) values (:id, :json)", {
        "id": identity,
        "json": json
    })

@with_connection
@with_cursor
@with_retry
def read_config(name: Text) -> Union[Text, None]:
    results = localthreaddb.cur.execute("select value from bowtie_config where name = :name", {"name": name}).fetchone()
    if results and len(results) > 0:
        return results[0]
    return None

@with_connection
@with_cursor
@with_retry
def set_config(name: Text, value: Text) -> None:
    if read_config(name) is None:
        localthreaddb.cur.execute("insert into bowtie_config(name, value) values (:name, :value)", {"name": name, "value": value})
    else:
        localthreaddb.cur.execute("update bowtie_config set value = :value where name = :name", {"name": name, "value": value})

@with_connection
@with_cursor
def init() -> None:
    cur = localthreaddb.cur
    cur.execute("create table if not exists bowtie_config (name text primary key, value text)")
    cur.execute("create table if not exists bowtie_entry (id integer primary key autoincrement, date int, content text, photo text, entities text, display_name text, icon text)")
    cur.execute("create index if not exists bowtie_entry_date on bowtie_entry(date)")
    cur.execute("create table if not exists bowtie_asset (id integer primary key autoincrement, source text, variant text, destination text)")
    cur.execute("create index if not exists bowtie_asset_source on bowtie_asset(source, variant)")
    cur.execute("create table if not exists bowtie_tweet (id int primary key, json text)")
