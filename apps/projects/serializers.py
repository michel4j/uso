from django.urls import reverse
from django.utils.text import slugify
from rest_framework import serializers

from . import models


class BeamTimeSerializer(serializers.ModelSerializer):
    rendering = serializers.SerializerMethodField()
    display = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    project_type = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()

    class Meta:
        model = models.BeamTime
        fields = (
            'id', 'start', 'end', 'name', 'tags', 'rendering', 'display',
            'project', 'project_type', 'description', 'url', 'section',
            'cancelled', 'comments'
        )

    def get_name(self, obj):
        return 'RESERVED' if not obj.project else obj.project.code()

    def get_description(self, obj):
        return 'RESERVED: {}'.format(obj.comments) if not obj.project else obj.project.__str__()

    def get_rendering(self, obj):
        return 'beamtime'

    def get_display(self, obj):
        return self.get_description(obj)

    def get_project_type(self, obj):
        return "reservation" if not obj.project else obj.project.kind

    def get_url(self, obj):
        return "" if not obj.project else reverse('project-detail', kwargs={'pk': obj.project.pk})

    def get_section(self, obj):
        return slugify(obj.beamline.acronym, allow_unicode=True)


class RequestBeamTimeSerializer(serializers.ModelSerializer):
    def get_rendering(self, obj):
        return 'busy'


class ProjectBeamTimeSerializer(BeamTimeSerializer):
    def get_display(self, obj):
        return obj.beamline.acronym
