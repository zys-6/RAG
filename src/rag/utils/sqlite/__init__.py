import pathlib
from .sqlite_client import SQLiteClient

DB_PATH = pathlib.Path(__file__).parent.parent.parent / 'resources' / 'sqlite.db'
sqlite_client = SQLiteClient(str(DB_PATH))