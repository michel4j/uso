from django.db import models


class Age(models.Func):
    function = 'MONTH'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT", template="%(function)s(month FROM %(expressions)s)/3600")

    def as_mysql(self, compiler, connection):
        self.arg_joiner = " , "
        return self.as_sql(compiler, connection, function="TIMESTAMPDIFF", template="-%(function)s(MONTH,%(expressions)s)")


class Hours(models.Func):
    function = 'HOUR'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT", template="%(function)s(epoch FROM %(expressions)s)/3600")

    def as_mysql(self, compiler, connection):
        self.arg_joiner = " , "
        return self.as_sql(compiler, connection, function="TIMESTAMPDIFF", template="-%(function)s(HOUR,%(expressions)s)")


class Shifts(models.Func):
    function = 'HOUR'
    template = '%(function)s(%(expressions)s)'

    def as_postgresql(self, compiler, connection):
        self.arg_joiner = " - "
        return self.as_sql(compiler, connection, function="EXTRACT", template="(%(function)s(epoch FROM %(expressions)s)/28800)")

    def as_mysql(self, compiler, connection):
        self.arg_joiner = " , "
        return self.as_sql(compiler, connection, function="TIMESTAMPDIFF", template="-%(function)s(HOUR,%(expressions)s)/8")


class Year(models.Func):
    function = 'YEAR'
    template = '%(function)s(%(expressions)s)'

    def as_sqlite(self, compiler, connection):
        # the template string needs to escape '%Y' to make sure it ends up in the final SQL. Because two rounds of
        # template parsing happen, it needs double-escaping ("%%%%").
        return self.as_sql(compiler, connection, function="strftime", template="%(function)s(\"%%%%Y\",%(expressions)s)")

    def as_postgresql(self, compiler, connection):
        return self.as_sql(compiler, connection, function="DATE_PART", template="%(function)s('YEAR', %(expressions)s)")


class String(models.Func):
    """
    Coerce an expression to a string.
    """
    function = 'CAST'
    template = '%(function)s(%(expressions)s AS varchar)'

    # def as_postgresql(self, compiler, connection):
    #     # CAST would be valid too, but the :: shortcut syntax is more readable.
    #     return self.as_sql(compiler, connection, template='%(expressions)s::char')


class LPad(models.Func):
    function = 'LPAD'
    template = "%(function)s(%(expressions)s)"

    def __init__(self, expression, length, **extra):
        super(LPad, self).__init__(expression, models.Value(length), models.Value('0'), **extra)
