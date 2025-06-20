from rest_framework import status
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Min, Max, F, ExpressionWrapper, fields

DURATION_FIELD = ExpressionWrapper(F('end') - F('start'), output_field=fields.DurationField())


def round_time(dt, delta):
    """Round a datetime object to any time laps
    dt : datetime.datetime object, default now.
    """
    seconds = (dt - dt.replace(hour=0, minute=0, second=0, microsecond=0)).seconds
    rounding = (seconds // delta.seconds) * delta.seconds
    return dt + timedelta(0, rounding - seconds, -dt.microsecond)


def create_event(schedule, queryset, data):
    # Do not create events which start or end outside of schedule
    data['schedule'] = schedule
    tags = data.pop('tags', [])
    if data['start'].date() < schedule.start_date or data['end'].date() > schedule.end_date:
        return status.HTTP_304_NOT_MODIFIED

    fields_filter = Q(cancelled=False, **{k: v for k, v in list(data.items()) if k not in ['start', 'end']})
    tags_filter = Q(**{'tags': v for v in tags})
    merge_filter = fields_filter & tags_filter

    queryset.filter(start__gte=data['start'], end__lte=data['end']).delete()  # Delete to Replace

    inside = queryset.filter(start__lt=data['start'], end__gt=data['end'])
    right = queryset.filter(end__gte=data['start'], end__lte=data['end'], start__lte=data['start'])
    left = queryset.filter(start__gte=data['start'], start__lte=data['end'], end__gte=data['end'])

    right_clip, left_clip = right.exclude(merge_filter), left.exclude(merge_filter)
    right_extend, left_extend = right.filter(merge_filter), left.filter(merge_filter)
    split = inside.exclude(merge_filter)

    left_clip.update(start=data['end'])
    right_clip.update(end=data['start'])

    if split.exists():
        for event in split.all():
            queryset.filter(pk=event.pk).update(end=data['start'])
            old_tags = event.tags.all()
            event.pk = None  # create copy
            event.start = data['end']
            event.save()
            event.tags.add(*old_tags)
        obj = queryset.create(**data)
        obj.tags.add(*tags)
        return status.HTTP_201_CREATED

    if right_extend.count() and left_extend.count():
        info = (right_extend | left_extend).all().aggregate(min_start=Min('start'), max_end=Max('end'))
        right_extend.delete()
        left_extend.delete()
        data.update(start=info['min_start'], end=info['max_end'])
        obj = queryset.create(**data)
        obj.tags.add(*tags)
        return status.HTTP_201_CREATED

    if right_extend.count() or left_extend.count() or inside.filter(merge_filter).count():
        right_extend.update(end=data['end'])
        left_extend.update(start=data['start'])
        return status.HTTP_202_ACCEPTED

    obj = queryset.create(**data)
    obj.tags.add(*tags)
    return status.HTTP_201_CREATED


def cancel_event(schedule, queryset, data):
    # calculate schedule limits
    limits = {
        'start': timezone.make_aware(datetime.combine(schedule.start_date, datetime.min.time())),
        'end': timezone.make_aware(datetime.combine(schedule.end_date, datetime.min.time())),
    }

    # set all events within range not already cancelled to cancel
    queryset.within(data).update(cancelled=True)

    # if request is enclosed within range events need to be split into 3
    splits = queryset.encloses(data).exclude(cancelled=True)
    if splits.exists():
        for event in splits.all():
            queryset.filter(pk=event.pk).update(end=data['start'])
            old_tags = event.tags.all()
            event.pk = None  # create split copy
            event.start = data['end']
            event.save()
            event.tags.add(*old_tags)
            event.pk = None  # now fill inside with cancelled
            event.start = data['start']
            event.end = data['end']
            event.cancelled = True
            event.save()
            event.tags.add(*old_tags)

    right = queryset.endswithin(data).exclude(cancelled=True)
    if right.exists():
        for event in right.all():
            old_end = event.end
            queryset.filter(pk=event.pk).update(end=data['start'])
            old_tags = event.tags.all()
            event.pk = None  # create copy
            event.start = data['start']
            event.end = old_end
            event.cancelled = True
            event.save()
            event.tags.add(*old_tags)

    left = queryset.startswithin(data).exclude(cancelled=True)
    if left.exists():
        for event in left.all():
            old_start = event.start
            queryset.filter(pk=event.pk).update(start=data['end'])
            old_tags = event.tags.all()
            event.pk = None  # create copy
            event.start = old_start
            event.end = data['end']
            event.cancelled = True
            event.save()
            event.tags.add(*old_tags)

    return status.HTTP_200_OK


def clear_event(schedule, queryset, data):
    # remove fully enclosed events
    queryset.within(data).delete()

    # Left and right clip
    queryset.startswithin(data).update(start=data['end'])
    queryset.endswithin(data).update(end=data['start'])

    # split
    split = queryset.encloses(data)
    if split.exists():
        for event in split.all():
            queryset.filter(pk=event.pk).update(end=data['start'])
            event.pk = None  # create copy
            event.start = data['end']
            event.save()
    return status.HTTP_200_OK
