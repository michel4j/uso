from django.db import models, connection


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


def aggregate_feedback_details_db(queryset):
    """
    Aggregates feedback details using database-level JSON functions.

    This approach pushes the heavy lifting of aggregation to the database,
    which can be significantly more performant than the pure Python approach
    for very large datasets, as it avoids loading the entire 'details' JSON
    object for every row into application memory.

    NOTE: The raw SQL implementation below uses `jsonb_array_elements`, a feature
    specific to PostgreSQL. It will not work on other database backends like
    SQLite or MySQL without modification.

    Args:
        queryset: A Django QuerySet of Feedback objects.

    Returns:
        A dictionary containing the aggregated sum, count, and average
        for each category.
    """
    # In this database-centric approach, it's often simpler to define the
    # categories you want to aggregate beforehand. Dynamically discovering all
    # possible keys would require a separate, more complex query.
    categories = ['machine', 'beamline', 'amenities']
    final_aggregates = {}

    # Get the database table name from the model's metadata to make the
    # query more robust and not dependent on a hardcoded name.
    table_name = queryset.model._meta.db_table

    # We need the primary keys from the queryset to scope the raw SQL query.
    queryset_pks = list(queryset.values_list('pk', flat=True))

    # If the queryset is empty, there's nothing to aggregate.
    if not queryset_pks:
        return {}

    with connection.cursor() as cursor:
        for category in categories:
            # This raw SQL query performs the entire aggregation for one category.
            # - `jsonb_array_elements(details->%s)`: Unnests the JSON array
            #   for the given category into a set of virtual rows.
            # - `(item->>'value')::integer`: Extracts the 'value' field as text
            #   and casts it to an integer for mathematical operations.
            # - `WHERE id = ANY(%s)`: Filters the aggregation to only include
            #   records from the provided queryset.
            # - `COALESCE(..., 0)`: Ensures we get 0 instead of NULL if there's
            #   no data to aggregate.
            sql_query = f"""
                SELECT
                    COALESCE(SUM((item->>'value')::integer), 0),
                    COALESCE(COUNT(item), 0)
                FROM
                    {table_name},
                    jsonb_array_elements(details->%s) AS item
                WHERE
                    {table_name}.id = ANY(%s)
            """
            cursor.execute(sql_query, [category, queryset_pks])
            row = cursor.fetchone()

            total_sum, total_count = row[0], row[1]

            final_aggregates[category] = {
                'sum': total_sum,
                'count': total_count,
                'average': round(total_sum / total_count, 2) if total_count > 0 else 0
            }

    return final_aggregates


class JSONExpand(models.Func):
    function = 'jsonb_array_elements'
    template = '%(function)s(%(expressions)s)'
    output_field = models.JSONField()


class JSONAvg(models.Func):
    """
    Joins an array of strings into a single string with a specified separator.
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
