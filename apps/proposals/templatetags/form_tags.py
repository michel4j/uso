from django import template

register = template.Library()


@register.filter(name='get_category')
def get_category(choices, cat):
    choice_iterator, choice_name = cat
    return choices.queryset.filter(category__pk=choice_iterator.value).values_list('pk', 'name')


@register.filter(name='get_pks')
def get_pks(qset):
    return [q.pk for q in qset]
