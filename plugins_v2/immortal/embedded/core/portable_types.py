"""Array expressions owned by Immortal, portable between SQLite and PostgreSQL.

SQLite stores arrays as JSON and compares individual JSON members, never substrings.
All custom compilers apply only to these plugin expression classes.
"""
from __future__ import annotations

import json
import re

from sqlalchemy import BigInteger, Boolean, Integer, JSON, String, bindparam, false
from sqlalchemy.dialects.postgresql import ARRAY as PostgreSQLArray
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import TypeDecorator


PrimaryKeyInteger = BigInteger().with_variant(Integer(), "sqlite")
FALSE_DEFAULT = false()


class PortableArray(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, item_type=String, **kwargs):
        self.item_type = item_type() if isinstance(item_type, type) else item_type
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQLArray(self.item_type))
        return dialect.type_descriptor(JSON(none_as_null=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, (list, tuple)):
            raise ValueError("数组字段必须是列表")
        return list(value)

    class Comparator(TypeDecorator.Comparator):
        def overlap(self, other):
            return _ArrayOverlap(self.expr, _array_value(other, self.type.item_type))

        def contains(self, other, **kwargs):
            return _ArrayContains(self.expr, _array_value(other, self.type.item_type))

    comparator_factory = Comparator


# Keep the original model declarations while using a plugin-owned portable type.
ARRAY = PortableArray


def _array_value(value, item_type=String):
    if isinstance(value, (list, tuple)) or value is None:
        return bindparam(None, value, type_=PortableArray(item_type))
    return value


class _ArrayOverlap(FunctionElement):
    type = Boolean()
    inherit_cache = True


class _ArrayContains(FunctionElement):
    type = Boolean()
    inherit_cache = True


class _ArrayMember(FunctionElement):
    type = Boolean()
    inherit_cache = True


class _ArrayAnyILike(FunctionElement):
    type = Boolean()
    inherit_cache = True


class _ArrayToString(FunctionElement):
    type = String()
    inherit_cache = True


class _ArrayPosition(FunctionElement):
    type = Integer()
    inherit_cache = True


def array_member(column, value):
    return _ArrayMember(column, value)


def array_any_ilike(column, pattern):
    return _ArrayAnyILike(column, pattern)


def array_to_string(column, separator=" "):
    return _ArrayToString(column, separator)


def array_position(values, value):
    return _ArrayPosition(_array_value(values, BigInteger()), value)


def _args(element, compiler, **kwargs):
    return [compiler.process(clause, **kwargs) for clause in element.clauses]


@compiles(_ArrayOverlap, "postgresql")
def _pg_overlap(element, compiler, **kwargs):
    left, right = _args(element, compiler, **kwargs)
    return f"({left} && {right})"


@compiles(_ArrayOverlap, "sqlite")
def _sqlite_overlap(element, compiler, **kwargs):
    left, right = _args(element, compiler, **kwargs)
    return (f"CASE WHEN {left} IS NULL OR {right} IS NULL THEN NULL ELSE EXISTS "
            f"(SELECT 1 FROM json_each({left}) AS immortal_left "
            f"JOIN json_each({right}) AS immortal_right "
            "ON immortal_left.value = immortal_right.value) END")


@compiles(_ArrayContains, "postgresql")
def _pg_contains(element, compiler, **kwargs):
    left, right = _args(element, compiler, **kwargs)
    return f"({left} @> {right})"


@compiles(_ArrayContains, "sqlite")
def _sqlite_contains(element, compiler, **kwargs):
    left, right = _args(element, compiler, **kwargs)
    return (f"CASE WHEN {left} IS NULL OR {right} IS NULL THEN NULL ELSE NOT EXISTS "
            f"(SELECT 1 FROM json_each({right}) AS immortal_required WHERE NOT EXISTS "
            f"(SELECT 1 FROM json_each({left}) AS immortal_member "
            "WHERE immortal_member.value = immortal_required.value)) END")


@compiles(_ArrayMember, "postgresql")
def _pg_member(element, compiler, **kwargs):
    column, value = _args(element, compiler, **kwargs)
    return f"({value} = ANY({column}))"


@compiles(_ArrayMember, "sqlite")
def _sqlite_member(element, compiler, **kwargs):
    column, value = _args(element, compiler, **kwargs)
    return (f"EXISTS (SELECT 1 FROM json_each({column}) AS immortal_member "
            f"WHERE immortal_member.value = {value})")


@compiles(_ArrayAnyILike, "postgresql")
def _pg_any_ilike(element, compiler, **kwargs):
    column, pattern = _args(element, compiler, **kwargs)
    return (f"EXISTS (SELECT 1 FROM unnest({column}) AS immortal_member(value) "
            f"WHERE immortal_member.value ILIKE {pattern})")


@compiles(_ArrayAnyILike, "sqlite")
def _sqlite_any_ilike(element, compiler, **kwargs):
    column, pattern = _args(element, compiler, **kwargs)
    return (f"EXISTS (SELECT 1 FROM json_each({column}) AS immortal_member "
            f"WHERE lower(immortal_member.value) LIKE lower({pattern}))")


@compiles(_ArrayToString, "postgresql")
def _pg_to_string(element, compiler, **kwargs):
    column, separator = _args(element, compiler, **kwargs)
    return f"array_to_string({column}, {separator})"


@compiles(_ArrayToString, "sqlite")
def _sqlite_to_string(element, compiler, **kwargs):
    column, separator = _args(element, compiler, **kwargs)
    return f"immortal_array_to_string({column}, {separator})"


@compiles(_ArrayPosition, "postgresql")
def _pg_position(element, compiler, **kwargs):
    column, value = _args(element, compiler, **kwargs)
    return f"array_position({column}, {value})"


@compiles(_ArrayPosition, "sqlite")
def _sqlite_position(element, compiler, **kwargs):
    column, value = _args(element, compiler, **kwargs)
    return f"immortal_array_position({column}, {value})"


def _json_array(value):
    if value is None:
        return None
    parsed = json.loads(value) if isinstance(value, str) else value
    return parsed if isinstance(parsed, list) else None


def install_sqlite_functions(connection):
    """Register helpers on this plugin's DB connection, not on platform SQLite."""
    def stringify(value, separator):
        values = _json_array(value)
        if values is None or separator is None:
            return None
        return str(separator).join(str(item) for item in values if item is not None)

    def position(value, item):
        values = _json_array(value)
        if values is None:
            return None
        for index, candidate in enumerate(values, 1):
            if candidate == item and (candidate is None or type(candidate) is type(item)):
                return index
        return None

    def replace(value, pattern, replacement, flags):
        if value is None:
            return None
        return re.sub(pattern, replacement, str(value), count=0 if "g" in str(flags) else 1)

    connection.create_function("immortal_array_to_string", 2, stringify, deterministic=True)
    connection.create_function("immortal_array_position", 2, position, deterministic=True)
    connection.create_function("regexp_replace", 4, replace, deterministic=True)
    connection.create_function("lower", 1, lambda value: str(value).lower() if value is not None else None,
                               deterministic=True)
