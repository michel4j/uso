from rest_framework import generics
from rest_framework import serializers
from django.db.models import Q
from . import models


class PublicationSerializer(serializers.ModelSerializer):
    cite = serializers.ReadOnlyField(source='citation')

    class Meta:
        model = models.Publication
        fields = ('cite', 'date')


class PublicationListAPI(generics.ListAPIView):
    serializer_class = PublicationSerializer
    model = models.Publication

    def get_queryset(self):
        """
        This view should return a list of all the publications in the
        category for the facility as determined by the facility and 
        category portions of the URL.
        """
        facility = self.kwargs['facility']
        category = self.kwargs.get('category', '')

        flt_grp = {'beamlines__parent__acronym__iexact': facility}
        flt_main = {'beamlines__acronym__iexact': facility}
        if category:
            flt_grp.update(kind__iexact=category)
            flt_main.update(kind__iexact=category)

        return self.model.objects.filter(Q(**flt_main) | Q(**flt_grp)).distinct().order_by('-year', 'authors')


class RecentSerializer(PublicationSerializer):
    cite = serializers.ReadOnlyField(source='short_citation')


class RecentListAPI(generics.ListAPIView):
    serializer_class = RecentSerializer
    model = models.Article
    paginate_by = 3

    def get_queryset(self):
        """
        This view should return a list of the most recent 3 articles 
        for the facility as determined by the facility portion of the URL.
        """
        facility = self.kwargs['facility']

        flt_grp = {'beamlines__parent__acronym__iexact': facility, 'kind__iexact': models.Article.TYPES.article}
        flt_main = {'beamlines__acronym__iexact': facility, 'kind__iexact': models.Article.TYPES.article}

        return self.model.objects.filter(Q(**flt_main) | Q(**flt_grp)).distinct().order_by('-date')


class CategorySerializer(serializers.ModelSerializer):
    display = serializers.SerializerMethodField('get_kind_display')

    class Meta:
        model = models.Publication
        fields = ('kind', 'display')

    def get_kind_display(self, obj):
        display = [v for k, v in models.Publication.TYPES if k == obj['kind']]
        return display[0]


class CategoryListAPI(generics.ListAPIView):
    serializer_class = CategorySerializer
    model = models.Publication

    def get_queryset(self):
        """
        This view should return a distinct list of all the categories 
        of publications for the facility as determined by the facility
        portion of the URL.
        """
        facility = self.kwargs['facility']
        flt = {'beamlines__acronym__icontains': facility}
        return self.model.objects.filter(**flt).values('kind').distinct()
