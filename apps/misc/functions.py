from __future__ import annotations

from django.core.exceptions import FieldError, FieldDoesNotExist
from django.db import models
from django.db.models import Subquery, OuterRef, Min, Max, Count, Avg, Sum, Expression
from django.db.models import Value, F


class Hours(models.Func):
    function = 'HOUR'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT",
                           template="%(function)s(epoch FROM %(expressions)s)/3600")


class Shifts(models.Func):
    function = 'HOUR'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT",
                           template="(%(function)s(epoch FROM %(expressions)s)/28800)")


class Year(models.Func):
    function = 'YEAR'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        return self.as_sql(compiler, connection, function="DATE_PART", template="%(function)s('YEAR', %(expressions)s)")


class String(models.Func):
    """
    Coerce an expression to a string.
    """
    function = 'CAST'
    template = '%(function)s(%(expressions)s AS varchar)'
    output_field = models.CharField()

    def as_postgresql(self, compiler, connection):
        # CAST would be valid too, but the :: shortcut syntax is more readable.
        return self.as_sql(compiler, connection, template='%(expressions)s::text')


class Float(models.Func):
    """
    Coerce an expression to a string.
    """
    function = 'CAST'
    template = '%(function)s(%(expressions)s AS varchar)'
    output_field = models.FloatField()

    def as_postgresql(self, compiler, connection):
        # CAST would be valid too, but the :: shortcut syntax is more readable.
        return self.as_sql(compiler, connection, template='%(expressions)s::float')


class LPad(models.Func):
    function = 'LPAD'
    template = "%(function)s(%(expressions)s)"

    def __init__(self, expression, length, **extra):
        super().__init__(expression, models.Value(length), models.Value('0'), **extra)


class JoinArray(models.Func):
    """
    Joins an array of strings into a single string with a specified separator.
    """

    output_field = models.CharField()

    def __init__(self, expression, separator=',', **extra):
        """
        :param expression: The JSONB array to join.
        :param separator: The string to use as a separator between elements.
        :param extra: Additional keyword arguments for the function.
        """
        self.separator = str(separator.value) if isinstance(separator, models.Value) else str(separator)
        super().__init__(expression, separator=models.Value(separator), **extra)

    def as_postgresql(self, compiler, connection):
        return self.as_sql(
            compiler,
            connection,
            function="jsonb_array_to_string",
            separator=self.separator,
            template="jsonb_array_to_string(%(expressions)s, '%(separator)s')"
        )


class ArrayLength(models.Func):
    """
    Calculates the length of a JSONB array.
    """
    output_field = models.IntegerField()

    def as_postgresql(self, compiler, connection):
        return self.as_sql(
            compiler, connection, function="jsonb_array_length", template="jsonb_array_length(%(expressions)s)"
        )


class ArrayItems(models.Func):
    """
    Concatenates JSONB arrays into a single array.
    """
    output_field = models.JSONField()

    def as_postgresql(self, compiler, connection):
        return self.as_sql(
            compiler, connection, function="jsonb_array_elements", template="jsonb_array_elements(%(expressions)s)"
        )


class JoinIt(models.Func):
    allow_distinct = True
    output_field = models.TextField()

    def __init__(self, expression, separator=', ', **extra):
        """
        A custom Django database function to join strings with a delimiter.
        :param expression: The field to join
        :param delimiter: The delimiter to use for joining
        :param extra: Additional arguments for the StringAgg function
        """
        self.delimiter = str(separator.value) if isinstance(separator, models.Value) else str(separator)
        super().__init__(expression, delimiter=self.delimiter, **extra)

    def as_postgresql(self, compiler, connection, **kwargs):
        return self.as_sql(
            compiler, connection,
            function="STRING_AGG",
            delimiter=models.Value(self.delimiter),
            template="%(function)s(%(distinct)s%(expressions)s %(order_by)s)",
            **kwargs
        )

    def as_sqlite(self, compiler, connection, **kwargs):
        return self.as_sql(
            compiler, connection,
            function="STRING_AGG",
            delimiter=models.Value(self.delimiter),
            template="%(function)s(%(expressions)s, '%(delimiter)s')",
            **kwargs
        )


class JSONExpand(models.Func):
    function = 'jsonb_array_elements'
    template = '%(function)s(%(expressions)s)'
    output_field = models.JSONField()


class JSONAvg(models.Func):
    """
    Average a value from objects in a JSONB array.
    """

    output_field = models.FloatField()

    def __init__(self, expressions, array_key, value_key, **extra):
        self.array_key = str(array_key.value) if isinstance(array_key, models.Value) else str(array_key)
        self.value_key = str(value_key.value) if isinstance(value_key, models.Value) else str(value_key)
        super().__init__(expressions, array_key=array_key, value_key=value_key, **extra)

    def as_postgresql(self, compiler, connection):
        return self.as_sql(
            compiler,
            connection,
            function="jsonb_array_avg",
            array_key=self.array_key,
            value_key=self.value_key,
            template="jsonb_array_avg(%(expressions)s, '%(array_key)s', '%(value_key)s')"
        )


class Age(models.Func):
    """
    Custom database function to calculate the age (as an interval)
    from a given date or datetime field to now.

    This function is specific to PostgreSQL and uses the AGE() function.

    Returns:
        models.DurationField: The interval between the field and the current time.
    """
    function = 'AGE'
    template = '%(function)s(%(expressions)s)'
    output_field = models.DurationField()


class AgeYears(models.Func):
    """
    Custom database function to calculate the number of full years
    from a given date or datetime field to now.

    This function is specific to PostgreSQL. It extracts the YEAR
    component from the result of the AGE() function.

    Returns:
        models.IntegerField: The total number of years as an integer.
    """
    template = "EXTRACT(YEAR FROM AGE(%(expressions)s))::integer"
    output_field = models.IntegerField()


class AgeMonths(models.Func):
    """
    Custom database function to calculate the total number of months
    from a given date or datetime field to now.

    This function is specific to PostgreSQL. It calculates total months by
    multiplying the years by 12 and adding the months from the AGE() result.

    Returns:
        models.IntegerField: The total number of months as an integer.
    """
    template = "((EXTRACT(YEAR FROM AGE(%(expressions)s)) * 12) + EXTRACT(MONTH FROM AGE(%(expressions)s)))::integer"
    output_field = models.IntegerField()


class Quarter(models.Func):
    """
    Custom database function to get the quarter name from a date/datetime field.
    For example, for a date of '2025-09-10', it returns '2025 Q3'.

    This function is specific to PostgreSQL.

    Returns:
        models.CharField: The formatted quarter string.
    """
    template = "CONCAT(EXTRACT(YEAR FROM %(expressions)s), ' Q', EXTRACT(QUARTER FROM %(expressions)s))"
    output_field = models.CharField()


class YearMonth(models.Func):
    """
    Custom database function to get the month name from a date/datetime field.
    For example, for a date of '2025-09-10', it returns '2025-09'.

    This function is specific to PostgreSQL.

    Returns:
        models.CharField: The formatted quarter string.
    """
    template = "TO_CHAR(%(expressions)s, 'YYYY-MM')"
    output_field = models.CharField()


class SplitPart(models.Func):
    """
    A custom database function for Django that mimics the behavior of
    PostgreSQL's SPLIT_PART function. It splits a string expression
    by a given delimiter and returns the nth substring.

    Usage:
    MyModel.objects.annotate(
        part=SplitPart('my_field', '.', 2)
    )
    """
    function = 'SPLIT_PART'
    arity = 3
    template = '%(function)s(%(expressions)s)'
    output_field = models.CharField()

    def __init__(self, expression, delimiter, position, **extra):
        """
        Initializes the SplitPart function.
        :param expression: The field or expression to split.
        :param delimiter: The delimiter to split the string by.
        :param position: The 1-based index of the part to return.
        :param extra: Additional options for the Func.
        """
        # Ensure delimiter and position are treated as literal values in the SQL query.
        delimiter_expr = Value(str(delimiter))
        position_expr = Value(int(position))
        super().__init__(expression, delimiter_expr, position_expr, **extra)


class RootValue(models.Expression):
    """
    Traverses a self-referencing foreign key to find the root object in a hierarchy and returns the value of a
    specified field from it. Designed for databases that support recursive Common Table Expressions.

    :param parent_field: The name of the self-referencing ForeignKey field that defines the hierarchy (e.g., 'parent').
                         Alternatively, an F() expression pointing to the start of a hierarchy on a related model.
    :param field_name: The name of the field on the root object whose value should be returned (e.g., 'name').

    Example Usage (Direct):
        # Annotates each category with the name of its own root.
        Category.objects.annotate(
            root_name=RootValue('parent', 'name')
        )

    Example Usage (with F() expression):
        # Assumes a Product model has a ForeignKey 'category' to Category,
        # and Category has a self-referencing key named 'parent'.
        Product.objects.annotate(
            root_category_name=RootValue(F('category'), 'name')
        )
        # NOTE: The recursive field name ('parent') is inferred from the
        #       related model's self-referencing key. For lookups like
        #       F('ingredient__category'), the recursive field name is
        #       assumed to be 'category'.
    """

    model: models.Model             # The model being queried, set during expression resolution.
    tree_model: models.Model        # The model where the hierarchy is defined.
    tree_parent_field: str          # The name of the self-referencing FK field on the hierarchy model.

    def __init__(self, parent_field: str | F, field_name: str | F, **kwargs):
        super().__init__(**kwargs)
        if not isinstance(parent_field, (str, F)):
            raise TypeError("'parent_field' must be a string or an F() expression.")
        if not isinstance(field_name, (str, F)):
            raise TypeError("'field_name' must be a string. or an F() expression.")

        self.parent_field = parent_field
        self.field_name = field_name if isinstance(field_name, str) else field_name.name

    def resolve_expression(self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False):
        resolved = self.copy()
        resolved.is_summary = summarize
        resolved.model = query.model    # keep a reference to the model the annotation is being applied to.

        # Determine if we are doing a simple lookup on the annotated model itself
        # or a more complex one starting from a related field.
        resolved.is_direct_lookup = isinstance(self.parent_field, str) and '__' not in self.parent_field
        parent_expression = self.parent_field if isinstance(self.parent_field, F) else F(self.parent_field)

        resolved.resolved_parent_expression = parent_expression.resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        target_field = resolved.resolved_parent_expression.target

        if resolved.is_direct_lookup:
            # For a direct lookup like RootValue('parent', ...), the hierarchy is on the model being queried.
            resolved.tree_model = query.model
        elif hasattr(target_field, 'related_model') and target_field.related_model:
            # For a lookup like RootValue(F('fk__parent'), ...), the hierarchy is on the related model.
            resolved.tree_model = target_field.related_model
        else:
            raise FieldError(
                f"The expression '{parent_expression.name}' does not resolve to a "
                "related field, which is required to find a hierarchy on another model."
            )

        # Infer the name of the self-referencing parent field on the hierarchy model
        # from the last part of the lookup.
        resolved.tree_parent_field = parent_expression.name.split('__')[-1]

        try:
            h_field = resolved.tree_model._meta.get_field(resolved.tree_parent_field)
            is_self_ref = (
                    h_field.is_relation and
                    h_field.related_model._meta.concrete_model == resolved.tree_model._meta.concrete_model
            )
            if not is_self_ref:
                raise FieldError()
        except (FieldDoesNotExist, FieldError):
            raise FieldError(
                f"Inferred parent field '{resolved.tree_parent_field}' either does not exist on "
                f"model '{resolved.tree_model._meta.object_name}' or is not a self-referencing ForeignKey."
            )

        resolved.output_field = resolved.tree_model._meta.get_field(self.field_name)
        return resolved

    def as_sql(self, compiler, connection):
        quote_name = connection.ops.quote_name

        meta = self.tree_model._meta
        table_name = meta.db_table

        pk_col = meta.pk.column
        parent_col = meta.get_field(self.tree_parent_field).column
        field_col = meta.get_field(self.field_name).column

        if self.is_direct_lookup:
            # On the hierarchical model itself, start traversal from the current row's PK.
            outer_alias = compiler.query.get_initial_alias()
            pk_col_on_outer_model = self.model._meta.pk.column
            start_node_sql = f'{quote_name(outer_alias)}.{quote_name(pk_col_on_outer_model)}'
            start_node_params = []
        else:
            # On a related model, the start of the traversal is the FK value from the F-expression.
            start_node_sql, start_node_params = compiler.compile(self.resolved_parent_expression)
            start_node_sql = f"({start_node_sql})"

        sql_template = """
        (WITH RECURSIVE __root_value_cte AS (
            SELECT
                T.%(pk)s as cte_pk,
                T.%(parent)s as cte_parent_pk,
                T.%(field)s as cte_field
            FROM %(table)s T
            WHERE T.%(pk)s = %(start_node_sql)s

            UNION ALL

            SELECT
                parent_table.%(pk)s,
                parent_table.%(parent)s,
                parent_table.%(field)s
            FROM %(table)s parent_table
            JOIN __root_value_cte child_cte ON parent_table.%(pk)s = child_cte.cte_parent_pk
        )
        SELECT cte_field
        FROM __root_value_cte
        WHERE cte_parent_pk IS NULL
        LIMIT 1)
        """

        params = {
            'table': quote_name(table_name),
            'pk': quote_name(pk_col),
            'parent': quote_name(parent_col),
            'field': quote_name(field_col),
            'start_node_sql': start_node_sql,
        }

        return sql_template % params, start_node_params


class SubAggregate(Expression):
    """
    A base class for creating subqueries that aggregate a single value from a
    related field.

    This expression acts as a factory. When resolved by the query compiler, it
    builds the appropriate queryset and returns a standard, resolved Subquery
    expression.
    """
    # Subclasses should override this with a Django aggregate class
    aggregate = None
    # The default alias for the aggregated value in the subquery's .values()
    aggregate_alias = 'agg'

    def __init__(self, expression, *args, **kwargs):
        """
        Initializes the expression.

        Args:
            expression (str): The field lookup to aggregate, e.g., 'sessions__start__year'.
            *args, **kwargs: Additional arguments passed to the aggregate function.
        """
        if not self.aggregate:
            raise NotImplementedError(
                "SubAggregate subclasses must define an 'aggregate' attribute."
            )

        self.expression = expression
        self.agg_args = args
        self.agg_kwargs = kwargs
        super().__init__()

    def resolve_expression(self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False):
        """
        Called by Django's query compiler to resolve the expression.

        This is where we build the actual subquery and return a standard,
        resolved Subquery object.
        """
        # 1. Get the model from the outer query (e.g., User)
        model = query.model

        # 2. Create the aggregate expression instance
        aggregate_expression = self.aggregate(
            self.expression, *self.agg_args, **self.agg_kwargs
        )

        # 3. Determine the output_field for the Subquery. If the user hasn't
        #    provided one, we must infer it from the aggregate expression.
        #    To do this, we resolve the aggregate against a query on the subquery's
        #    model to discover its output_field.

        # A lightweight query object for the model is all that's needed.
        subquery_model_query = model.objects.none().query
        resolved_aggregate = aggregate_expression.resolve_expression(
            query=subquery_model_query,
            allow_joins=True,
            reuse=None,
            summarize=True  # Aggregates must be resolved with summarize=True
        )
        output_field = resolved_aggregate.output_field

        # 4. Build the subquery queryset, linking it to the outer query
        sub_queryset = model.objects.filter(pk=OuterRef('pk'))
        sub_queryset = sub_queryset.values(
            **{self.aggregate_alias: aggregate_expression}
        )
        sub_queryset = sub_queryset[:1]

        # 5. Create a standard Subquery instance with the real queryset
        #    and the now-known output_field, then have it resolve itself.
        final_subquery = Subquery(sub_queryset, output_field=output_field)

        return final_subquery.resolve_expression(query, allow_joins, reuse, summarize, for_save)


class SubMin(SubAggregate):
    """Annotates with the minimum value of a related expression."""
    aggregate = Min


class SubMax(SubAggregate):
    """Annotates with the maximum value of a related expression."""
    aggregate = Max


class SubCount(SubAggregate):
    """Annotates with the count of a related expression."""
    aggregate = Count


class SubAvg(SubAggregate):
    """Annotates with the average value of a related expression."""
    aggregate = Avg


class SubSum(SubAggregate):
    """Annotates with the sum of a related expression."""
    aggregate = Sum
