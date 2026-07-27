import sqlglot
from sqlglot import expressions as exp


def append_filters(
    sql: str,
    dialect: str,
    filters: list[tuple[str, str | int | float]],
) -> str:
    try:
        parsed = sqlglot.parse_one(sql, read=dialect)
    except Exception:  # noqa: BLE001
        return sql

    select_expr = _get_top_level_select(parsed)
    if not select_expr:
        return sql

    table_name = _resolve_first_table_name(select_expr)
    for column_name, value in filters:
        if isinstance(value, str) and not value:
            continue

        if _has_equal_filter(select_expr, column_name=column_name, value=value):
            continue

        literal: exp.Literal
        if isinstance(value, (int, float)):
            literal = exp.Literal.number(str(value))
        else:
            literal = exp.Literal.string(value)

        condition = exp.EQ(
            this=_build_column(column_name=column_name, table_name=table_name),
            expression=literal,
        )

        where_clause = select_expr.args.get("where")
        if isinstance(where_clause, exp.Where) and where_clause.this is not None:
            where_clause.set("this", exp.and_(where_clause.this, condition))
        else:
            select_expr.set("where", exp.Where(this=condition))

    return parsed.sql(dialect=dialect)


def append_user_filter(sql: str, dialect: str, user_value: str, *, column_name: str = "user") -> str:
    return append_filters(sql, dialect=dialect, filters=[(column_name, user_value)])


def _get_top_level_select(parsed: exp.Expression) -> exp.Select | None:
    if isinstance(parsed, exp.Select):
        return parsed
    if isinstance(parsed, exp.With) and isinstance(parsed.this, exp.Select):
        return parsed.this
    return None


def _build_column(column_name: str, table_name: str | None) -> exp.Column:
    if table_name:
        return exp.Column(
            this=exp.Identifier(this=column_name),
            table=exp.Identifier(this=table_name),
        )
    return exp.Column(this=exp.Identifier(this=column_name))


def _resolve_first_table_name(select_expr: exp.Select) -> str | None:
    from_expr = select_expr.args.get("from")
    if not isinstance(from_expr, exp.From):
        return None

    for source in from_expr.expressions:
        if isinstance(source, exp.Table) and isinstance(source.name, str) and source.name:
            return source.name
    return None


def _has_equal_filter(select_expr: exp.Select, *, column_name: str, value: str | int | float) -> bool:
    where_clause = select_expr.args.get("where")
    if not isinstance(where_clause, exp.Where) or where_clause.this is None:
        return False

    for node in where_clause.this.walk():
        if not isinstance(node, exp.EQ):
            continue

        left = node.this
        right = node.expression
        if not isinstance(left, exp.Column) or not isinstance(right, exp.Literal):
            continue

        if left.name != column_name:
            continue

        if isinstance(value, (int, float)):
            if right.is_number and str(right.this) == str(value):
                return True
        else:
            if right.is_string and right.this == value:
                return True

    return False


if __name__ == '__main__':
    sql = "select * from user where id =123  and id2 =456 union select * from user1"

    di = "clickhouse"

    sql1 = "select * from user a"

    sql2 = "select * from user where id =123"

    sql3 = "select * from user order by create_time desc"

    sql_result = append_filters(sql=sql, dialect=di, filters=[("id", 1234)])
    sql1_result = append_filters(sql=sql1, dialect=di, filters=[("id", 123)])
    sql2_result = append_filters(sql=sql2, dialect=di, filters=[("id", 1243)])
    sql3_result = append_filters(sql=sql3, dialect=di, filters=[("id", 123)])

    print(sql_result)
    print(sql1_result)
    print(sql2_result)
    print(sql3_result)
