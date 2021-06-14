from django.db import models

from tumpara.accounts.models import MembershipHost


class Thing(MembershipHost):
    foo = models.CharField(max_length=100)
    bar = models.CharField(max_length=100)
