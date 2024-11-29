import copy

from django.utils.safestring import mark_safe
from prettytable import PrettyTable

DATA_COLORS = ['#7eb852', '#07997e', '#4f54a8', '#991c71', '#cf003e', '#e3690b', '#efb605', '#a5a5a5']


class DataTable(object):
    def __init__(
            self, t, heading="", sub_heading="", align="r", float_format='0.1',
            css_class="stats-table", max_cols=50, plot_limits=(None, None)
    ):
        self.table = t
        self.heading = heading
        self.sub_heading = sub_heading
        self.align = align
        self.float_format = float_format
        self.max_cols = max_cols
        self.plot_limits = plot_limits
        self.css_class = "{} table table-condensed".format(css_class)

    def __repr__(self):
        return "<Table ({0} rows, {1} columns)>".format(*self.size())

    def __str__(self):
        return self.text()

    def __getitem__(self, rk, ck):
        ci = self.table[0].index(rk)
        ri = list(zip(*self.tables))[0].index(ck)
        return self.table[ri][ci]

    def make_pretty(self):
        x = PrettyTable(self.table[0])
        x.float_format = self.float_format
        x.align[self.table[0][0]] = 'l'
        for c in self.table[0][1:]:
            x.align[str(c)] = self.align
        for row in self.table[1:]:
            x.add_row(row)
        return x

    def remove_columns(self, idxs):
        for i, r in enumerate(self.table):
            self.table[i] = [v for j, v in enumerate(r) if not j in idxs]

    def size(self):
        return len(self.table), len(self.table[0])

    def reverse(self):
        self.table = list(zip(*self.table))

    def text(self, full=False):
        full_text = ""
        for tbl in self.split(max_cols=self.max_cols):
            x = tbl.make_pretty()
            x = self.make_pretty()
            full_text += '\n' + x.get_string()
        return full_text

    def plot_data(self, color_scheme={}):
        last_row = self.plot_limits[0]
        last_col = self.plot_limits[1]
        data = []
        xlabels = self.table[0][1:last_col]
        for series in self.table[1:last_row]:
            dat = {
                'key': series[0],
                'values': [{'x': v[0], 'y': v[1]} for v in zip(xlabels, series[1:last_col])]
            }
            if color_scheme:
                dat['color'] = color_scheme.get(dat['key'], 'inherit')
            data.append(dat)
        return data

    def series(self):
        data = []
        xlabels = self.table[0][1:]
        for series in self.table[1:]:
            dat = {
                'name': series[0],
                'values': [[v[0], v[1]] for v in zip(xlabels, series[1:])],
                'total': sum(series[1:])
            }
            data.append(dat)
        return data

    def html(self, attrs=None):
        attrs = {} if not attrs else attrs
        full_html = ""
        attrs.update({"class": self.css_class})
        for tbl in self.split(max_cols=self.max_cols):
            x = tbl.make_pretty()
            x.border = False
            html = x.get_html_string(attributes=attrs, format=False)
            full_html += f"{html}\n"
        if self.heading:
            _sub = f"<span class='text-muted'>{self.sub_heading}</span><hr class='hr-xs'/>" if self.sub_heading else ""
            full_html = f"<h4 class='no-bmargin'><strong>{self.heading}</strong></h4>{_sub}\n{full_html}"

        return mark_safe(full_html)

    def split(self, max_cols=6):
        chunks = []
        tbl = copy.deepcopy(self)
        if tbl.size()[1] <= max_cols + 1:
            chunks.append(tbl)

        while tbl.size()[1] > max_cols + 1:
            tbl_left = copy.deepcopy(tbl)
            tbl.remove_columns(list(range(max_cols + 1, tbl.size()[1])))
            tbl_left.remove_columns(list(range(1, max_cols + 1)))
            chunks.append(tbl)
            tbl = tbl_left
            if tbl.size()[1] <= max_cols + 1:
                chunks.append(tbl)
        return chunks
