import json
import re
import sqlite3
import logging
from pathlib import Path
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def clean_identifier(name: str, fallback: str = "field") -> str:
    name = str(name).strip().lower()
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = fallback
    if name[0].isdigit():
        name = f"{fallback}_{name}"
    return name


def sql_type(value: Any) -> str:
    # legacy helper kept for callers that don't use configurable mapping
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int) and not isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    if value is None:
        return "TEXT"
    return "TEXT"


def _logical_type(value: Any) -> str:
    """Return a logical type name for a Python value: 'int','float','bool','string','null','object','array'."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (dict,)):
        return "object"
    if isinstance(value, (list,)):
        return "array"
    return "string"


def merge_sql_types(left: str, right: str) -> str:
    if left == right:
        return left
    if "TEXT" in (left, right):
        return "TEXT"
    if "REAL" in (left, right):
        return "REAL"
    return "INTEGER"


def value_for_sql(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


@dataclass
class TableSchema:
    name: str
    columns: dict[str, str] = field(default_factory=dict)
    parent_table: str | None = None

    @property
    def parent_fk(self) -> str | None:
        if self.parent_table is None:
            return None
        return f"{self.parent_table}_id"


class JsonSqlConverter:
    def __init__(self, database_path: str | Path = "converted_data.db") -> None:
        # minimal logger to aid debugging and demo runs
        self.logger = logging.getLogger("JsonSqlConverter")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            fmt = logging.Formatter("[%(levelname)s] %(message)s")
            handler.setFormatter(fmt)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.database_path = Path(database_path)
        # load optional type mapping configuration
        self._load_type_mapping()
        self.schemas: dict[str, TableSchema] = {}
        self.connection = sqlite3.connect(self.database_path)
        self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.connection.close()

    def reset_database(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF")
        tables = self.list_tables()
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
        cursor.execute("PRAGMA foreign_keys = ON")
        self.connection.commit()
        self.schemas.clear()

    def convert_file(self, json_path: str | Path, root_table: str = "root") -> None:
        path = Path(json_path)
        self.logger.info(f"Converting file: {path}")
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        root_name = clean_identifier(path.stem or root_table, root_table)
        self.convert_data(data, root_name)

    def convert_data(self, data: Any, root_table: str = "root") -> None:
        self.reset_database()
        root_table = clean_identifier(root_table, "root")
        root_rows = data if isinstance(data, list) else [data]

        if not root_rows:
            self._ensure_table(root_table)
        for item in root_rows:
            if isinstance(item, dict):
                self._analyze_object(root_table, item)
            else:
                self._analyze_object(root_table, {"value": item})

        self._create_tables()

        for item in root_rows:
            if isinstance(item, dict):
                self._insert_object(root_table, item)
            else:
                self._insert_object(root_table, {"value": item})

        self.connection.commit()

    def list_tables(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def _load_type_mapping(self) -> None:
        """Load type mapping from config/type_mapping.json if present. The mapping maps
        logical types (string,int,float,bool,null,object,array) to SQL types.
        """
        default = {
            "string": "TEXT",
            "int": "INTEGER",
            "float": "REAL",
            "bool": "INTEGER",
            "null": "TEXT",
            "object": "TEXT",
            "array": "TEXT",
        }
        try:
            config_path = Path(__file__).resolve().parent / "config" / "type_mapping.json"
            if config_path.exists():
                with config_path.open("r", encoding="utf-8") as fh:
                    user = json.load(fh)
                    default.update({k: v for k, v in user.items() if isinstance(k, str)})
        except Exception:
            pass
        self.type_map = default

    def _map_type(self, value: Any) -> str:
        """Map a Python value to a SQL type using the configured mapping."""
        logical = _logical_type(value)
        return self.type_map.get(logical, "TEXT")

    def table_rows(self, table_name: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        table_name = clean_identifier(table_name)
        cursor = self.connection.execute(f'SELECT * FROM "{table_name}"')
        columns = [description[0] for description in cursor.description]
        return columns, cursor.fetchall()

    def generated_schema_text(self) -> str:
        lines: list[str] = []
        for table_name in sorted(self.schemas):
            schema = self.schemas[table_name]
            lines.append(f"TABLE {table_name}")
            lines.append("  id INTEGER PRIMARY KEY AUTOINCREMENT")
            if schema.parent_fk:
                lines.append(f"  {schema.parent_fk} INTEGER FOREIGN KEY -> {schema.parent_table}(id)")
            for column, column_type in sorted(schema.columns.items()):
                # skip user-provided 'id' column to avoid duplicate PK column in display
                if column == 'id':
                    continue
                lines.append(f"  {column} {column_type}")
            lines.append("")
        return "\n".join(lines).strip()

    def _ensure_table(self, table_name: str, parent_table: str | None = None) -> TableSchema:
        table_name = clean_identifier(table_name, "table")
        if table_name not in self.schemas:
            self.schemas[table_name] = TableSchema(name=table_name, parent_table=parent_table)
        elif parent_table and self.schemas[table_name].parent_table is None:
            self.schemas[table_name].parent_table = parent_table
        return self.schemas[table_name]

    def _add_column(self, table_name: str, column_name: str, value: Any) -> None:
        schema = self._ensure_table(table_name)
        column_name = clean_identifier(column_name)
        detected_type = self._map_type(value)
        if column_name in schema.columns:
            schema.columns[column_name] = merge_sql_types(schema.columns[column_name], detected_type)
        else:
            schema.columns[column_name] = detected_type

    def _analyze_object(self, table_name: str, obj: dict[str, Any], prefix: str = "") -> None:
        self._ensure_table(table_name)
        for key, value in obj.items():
            safe_key = clean_identifier(key)
            effective_key = f"{prefix}_{safe_key}" if prefix else safe_key
            if isinstance(value, list):
                child_table = self._child_table_name(table_name, effective_key)
                self._ensure_table(child_table, table_name)
                for item in value:
                    if isinstance(item, dict):
                        self._analyze_object(child_table, item)
                    else:
                        self._analyze_object(child_table, {"value": item})
            elif isinstance(value, dict):
                self._analyze_object(table_name, value, effective_key)
            else:
                self._add_column(table_name, effective_key, value)

    def _flatten_object(self, prefix: str, obj: dict[str, Any]) -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        for key, value in obj.items():
            safe_key = clean_identifier(key)
            column_name = f"{prefix}_{safe_key}"
            if isinstance(value, dict):
                flattened.update(self._flatten_object(column_name, value))
            elif isinstance(value, list):
                continue
            else:
                flattened[column_name] = value
        return flattened

    def _create_tables(self) -> None:
        for table_name in self._tables_in_dependency_order():
            schema = self.schemas[table_name]
            self.logger.info(f"Creating table: {table_name} (parent={schema.parent_table})")
            definitions = ['"id" INTEGER PRIMARY KEY AUTOINCREMENT']
            if schema.parent_fk:
                definitions.append(f'"{schema.parent_fk}" INTEGER NOT NULL')
            for column_name, column_type in sorted(schema.columns.items()):
                # avoid adding a user-provided 'id' column since we create the PK ourselves
                if column_name == 'id':
                    continue
                definitions.append(f'"{column_name}" {column_type}')
            if schema.parent_fk:
                definitions.append(
                    f'FOREIGN KEY("{schema.parent_fk}") REFERENCES "{schema.parent_table}"("id") ON DELETE CASCADE'
                )
            sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(definitions)})'
            self.connection.execute(sql)

    def _tables_in_dependency_order(self) -> list[str]:
        ordered: list[str] = []
        visited: set[str] = set()

        def visit(table_name: str) -> None:
            if table_name in visited:
                return
            schema = self.schemas[table_name]
            if schema.parent_table and schema.parent_table in self.schemas:
                visit(schema.parent_table)
            visited.add(table_name)
            ordered.append(table_name)

        for name in sorted(self.schemas):
            visit(name)
        return ordered

    def _insert_object(
        self,
        table_name: str,
        obj: dict[str, Any],
        parent_id: int | None = None,
        prefix: str = "",
    ) -> int:
        schema = self.schemas[table_name]
        row: dict[str, Any] = {}

        if schema.parent_fk and parent_id is not None:
            row[schema.parent_fk] = parent_id

        for key, value in obj.items():
            safe_key = clean_identifier(key)
            effective_key = f"{prefix}_{safe_key}" if prefix else safe_key
            if isinstance(value, list):
                continue
            if isinstance(value, dict):
                for flat_key, flat_value in self._flatten_object(effective_key, value).items():
                    if flat_key in schema.columns:
                        row[flat_key] = value_for_sql(flat_value)
            elif effective_key in schema.columns:
                row[effective_key] = value_for_sql(value)

        columns = list(row.keys())
        if columns:
            placeholders = ", ".join("?" for _ in columns)
            column_sql = ", ".join(f'"{column}"' for column in columns)
            values = [row[column] for column in columns]
            cursor = self.connection.execute(
                f'INSERT INTO "{table_name}" ({column_sql}) VALUES ({placeholders})',
                values,
            )
        else:
            cursor = self.connection.execute(f'INSERT INTO "{table_name}" DEFAULT VALUES')

        current_id = int(cursor.lastrowid)

        for key, value in obj.items():
            safe_key = clean_identifier(key)
            effective_key = f"{prefix}_{safe_key}" if prefix else safe_key
            if not isinstance(value, list):
                if isinstance(value, dict):
                    self._insert_nested_arrays(table_name, value, current_id, effective_key)
                continue
            child_table = self._child_table_name(table_name, effective_key)
            for item in value:
                if isinstance(item, dict):
                    self._insert_object(child_table, item, current_id)
                else:
                    self._insert_object(child_table, {"value": item}, current_id)

        return current_id

    def _insert_nested_arrays(
        self,
        table_name: str,
        obj: dict[str, Any],
        parent_id: int,
        prefix: str,
    ) -> None:
        for key, value in obj.items():
            safe_key = clean_identifier(key)
            effective_key = f"{prefix}_{safe_key}" if prefix else safe_key
            if isinstance(value, list):
                child_table = self._child_table_name(table_name, effective_key)
                for item in value:
                    if isinstance(item, dict):
                        self._insert_object(child_table, item, parent_id)
                    else:
                        self._insert_object(child_table, {"value": item}, parent_id)
            elif isinstance(value, dict):
                self._insert_nested_arrays(table_name, value, parent_id, effective_key)

    def _child_table_name(self, parent_table: str, key: str) -> str:
        return clean_identifier(f"{parent_table}_{key}", "table")
