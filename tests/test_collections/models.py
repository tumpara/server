from django.db import models

from tumpara.accounts.models import MembershipHost
from tumpara.collections.models import Archivable, Collection, CollectionItem
from tumpara.storage.models import LibraryContent


class Thing(Archivable):
    pass


class ThingContainer(Collection):
    items = models.ManyToManyField(Thing, through="ThingContainerItem")


class ThingContainerItem(CollectionItem):
    collection = models.ForeignKey(ThingContainer, on_delete=models.CASCADE)
    content_object = models.ForeignKey(Thing, on_delete=models.CASCADE)


class ThingContainerMembers(Collection, MembershipHost, Archivable):
    items = models.ManyToManyField(Thing, through="ThingContainerMembersItem")


class ThingContainerMembersItem(CollectionItem):
    collection = models.ForeignKey(ThingContainerMembers, on_delete=models.CASCADE)
    content_object = models.ForeignKey(Thing, on_delete=models.CASCADE)


class MaybeHiddenThing(LibraryContent):
    pass
