from django.db import models
from django.db.models import Expression, OuterRef, F, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast


class Age(models.Func):
    function = 'MONTH'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT",
                           template="%(function)s(month FROM %(expressions)s)/3600")


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


class JsonArrayAggregate(models.Expression):
    """
    A custom Django Expression to aggregate a value from a list of dictionaries
    stored in a JSONField.

    It works by creating a subquery that:
    1. Un-nests the JSON array using PostgreSQL's `jsonb_array_elements`.
    2. Extracts the specified `key_name` from each dictionary element.
    3. Casts the extracted value to the specified `output_field`.
    4. Applies the provided `aggregator_class` (e.g., Avg, Sum) to the values.
    """
    def __init__(self, json_field, key_name, aggregator_class, output_field=models.FloatField(), **aggregator_kwargs):
        """
        Args:
            json_field (str): The name of the JSONField on the model.
            key_name (str): The key within each dictionary to aggregate.
            aggregator_class (Type[Aggregate]): The Django aggregation class (e.g., Avg, Sum, Max).
            output_field (Field): The Django model field to cast the value to.
            **aggregator_kwargs: Additional keyword arguments for the aggregator.
        """
        super().__init__(output_field=output_field)

        self.json_field = F(json_field) if isinstance(json_field, str) else json_field
        self.key_name = key_name
        self.aggregator_class = aggregator_class
        self.aggregator_kwargs = aggregator_kwargs

    def resolve_expression(self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False):
        """
        This method is called by Django during the query compilation phase.
        It constructs and returns a standard Subquery expression, effectively
        replacing itself with the resolved subquery.
        """
        # The model the annotation is being applied to (e.g., Product)
        model = query.model

        # Build the subquery that will be executed for each row of the main query.
        subquery = model.objects.filter(pk=OuterRef('pk')).annotate(
            # 1. Un-nest the JSON array. Use a unique alias to prevent collisions.
            _unnested_data=models.Func(self.json_field, function='jsonb_array_elements')
        ).annotate(
            # 2. Extract the key's value and cast it to the correct type.
            _casted_key_value=Cast(
                KeyTextTransform(self.key_name, '_unnested_data'),
                output_field=self.output_field
            )
        ).values('pk').annotate(
            # 3. Apply the final aggregation.
            aggregated_value=self.aggregator_class(
                '_casted_key_value', **self.aggregator_kwargs
            )
        ).values('aggregated_value')

        # The final expression is a Subquery. We resolve it to let Django handle it.
        return Subquery(subquery, output_field=self.output_field).resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )


class JsonAvg(JsonArrayAggregate):
    def __init__(self, json_field, key_name, **kwargs):
        super().__init__(json_field, key_name, models.Avg, output_field=models.FloatField(), **kwargs)


class JsonSum(JsonArrayAggregate):
    def __init__(self, json_field, key_name, **kwargs):
        super().__init__(json_field, key_name, models.Sum, output_field=models.FloatField(), **kwargs)


class JsonMax(JsonArrayAggregate):
    def __init__(self, json_field, key_name, **kwargs):
        super().__init__(json_field, key_name, models.Max, output_field=models.FloatField(), **kwargs)


class JsonMin(JsonArrayAggregate):
    def __init__(self, json_field, key_name, **kwargs):
        super().__init__(json_field, key_name, models.Min, output_field=models.FloatField(), **kwargs)
