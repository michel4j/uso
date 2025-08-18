from django.db import models


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