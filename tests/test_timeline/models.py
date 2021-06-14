from django.db import models

from tumpara.timeline.models import Entry

# Note: the reason this app requires migrations (unlike the other testing apps),
# is because it depends on the timeline app, which uses migrations. See here:
# https://docs.djangoproject.com/en/3.1/topics/migrations/#dependencies


class FooEntry(Entry):
    the_string = models.CharField(max_length=50)


class BarEntry(Entry):
    first_number = models.IntegerField()
    second_number = models.IntegerField()
