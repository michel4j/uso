from rest_framework import serializers

from . import models


class UserSupportSerializer(serializers.ModelSerializer):
    rendering = serializers.SerializerMethodField()
    display = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()

    class Meta:
        model = models.UserSupport
        fields = (
            'id', 'start', 'end', 'name', 'rendering', 'display',
            'description', 'section', 'tags',
            'cancelled', 'comments'
        )

    def get_name(self, obj):
        return obj.staff.initials()

    def get_description(self, obj):
        return obj.staff.get_full_name()

    def get_rendering(self, obj):
        return 'staff'

    def get_display(self, obj):
        return self.get_description(obj)

    def get_section(self, obj):
        return 'staff'
