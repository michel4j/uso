from django.db import models
from django.db.models.functions import Cast


class Age(models.Func):
    function = 'MONTH'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT",
                           template="%(function)s(month FROM %(expressions)s)/3600")

    def as_mysql(self, compiler, connection):
        self.arg_joiner = " , "
        return self.as_sql(compiler, connection, function="TIMESTAMPDIFF",
                           template="-%(function)s(MONTH,%(expressions)s)")


class Hours(models.Func):
    function = 'HOUR'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT",
                           template="%(function)s(epoch FROM %(expressions)s)/3600")

    def as_mysql(self, compiler, connection):
        self.arg_joiner = " , "
        return self.as_sql(compiler, connection, function="TIMESTAMPDIFF",
                           template="-%(function)s(HOUR,%(expressions)s)")


class Shifts(models.Func):
    function = 'HOUR'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT",
                           template="(%(function)s(epoch FROM %(expressions)s)/28800)")

    def as_mysql(self, compiler, connection):
        self.arg_joiner = " , "
        return self.as_sql(compiler, connection, function="TIMESTAMPDIFF",
                           template="-%(function)s(HOUR,%(expressions)s)/8")


class Year(models.Func):
    function = 'YEAR'
    template = '%(function)s(%(expressions)s)'

    def as_sqlite(self, compiler, connection):
        # the template string needs to escape '%Y' to make sure it ends up in the final SQL. Because two rounds of
        # template parsing happen, it needs double-escaping ("%%%%").
        return self.as_sql(compiler, connection, function="strftime",
                           template="%(function)s(\"%%%%Y\",%(expressions)s)")

    def as_postgresql(self, compiler, connection):
        return self.as_sql(compiler, connection, function="DATE_PART", template="%(function)s('YEAR', %(expressions)s)")


class LPad(models.Func):
    function = 'LPAD'
    template = "%(function)s(%(expressions)s)"

    def __init__(self, expression, length, **extra):
        super().__init__(expression, models.Value(length), models.Value('0'), **extra)


class JoinArray(models.Func):
    function = "ARRAY_TO_STRING"
    template = "%(function)s(%(expressions)s)"
    allow_distinct = True
    output_field = models.TextField()

    def __init__(self, expression, delimiter, **extra):
        if isinstance(delimiter, models.Value):
            delimiter_expr = delimiter
        else:
            delimiter_expr = models.Value(str(delimiter))
        super().__init__(expression, delimiter_expr, **extra)


class String(Cast):
    """
    Coerce an expression to a string.
    """
    output_field = models.CharField()

    def __init__(self, expression):
        super().__init__(expression, output_field=self.output_field)

