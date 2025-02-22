from rest_framework import serializers
from . import models
from datetime import datetime
from django.utils import timezone


class ModeSerializer(serializers.ModelSerializer):
    rendering = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    display = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    tentative = serializers.SerializerMethodField()

    class Meta:
        model = models.Mode
        fields = (
            'id', 'start', 'end', 'name', 'tags', 'cancelled',
            'rendering', 'display', 'kind', 'description', 'tentative'
        )

    def get_description(self, obj):
        return obj.comments

    def get_rendering(self, obj):
        return 'mode'

    def get_name(self, obj):
        return obj.kind

    def get_display(self, obj):
        return obj.kind

    def get_tentative(self, obj):
        return obj.schedule.state == obj.schedule.STATES.tentative
