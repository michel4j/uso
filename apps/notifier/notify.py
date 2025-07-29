import re

from django.conf import settings
from django.template import Template, Context

from . import models

LEVELS = models.Notification.LEVELS


def send(users, label, level=LEVELS.info, context=None, send_on=None):
    context = context if context is not None else {}
    from users.models import User

    message_template = models.MessageTemplate.objects.latest_for(label)
    if not message_template:
        raise Exception("No message template found for {}".format(label))

    template = Template(message_template.content)

    # get list of receivers
    user_list = [u for u in users if not isinstance(u, str)]
    email_list = [u for u in users if isinstance(u, str) and re.match(r"[^@]+@[^@]+\.[^@]+", u)]
    role_list = [u for u in users if
                 isinstance(u, str) and not re.match(r"[^@]+@[^@]+\.[^@]+", u)]  # non-email text is role
    role_users = [u for role in role_list for u in User.objects.all_with_roles(role)]

    for user in user_list + role_users:
        data = {
            "user": user,
            "site": getattr(settings, 'SITE_URL', ""),
        }
        data.update(context)
        message = template.render(Context(data))
        note = models.Notification.objects.create(user=user, kind=label, send_on=send_on, level=level, data=message)
        if not send_on:
            note.deliver()

    if email_list:
        data = {
            "emails": email_list,
            "site": getattr(settings, 'SITE_URL', ""),
        }
        data.update(context)
        message = template.render(Context(data))
        note = models.Notification.objects.create(emails=email_list, send_on=send_on, level=level, kind=label,
                                                  data=message)
        if not send_on:
            note.deliver()


def queue(users, label, send_on, level=LEVELS.info, context={}):
    return send(users, label, level=level, send_on=send_on, context=context)
