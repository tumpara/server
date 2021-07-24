import graphene
from django import forms
from django.db.models import QuerySet
from graphene import relay
from graphene_django import DjangoObjectType

from tumpara.accounts.api import MembershipHostObjectType
from tumpara.api import Subschema
from tumpara.api.util import CreateModelFormMutation, UpdateModelFormMutation

from . import models


class Thing(MembershipHostObjectType):
    class Meta:
        name = "TestApiThing"
        model = models.Thing


class ThingForm(forms.ModelForm):
    class Meta:
        model = models.Thing
        fields = ("foo", "bar")


class CreateThing(CreateModelFormMutation):
    class Meta:
        name = "TestApiCreateThing"
        form_class = ThingForm


class UpdateThing(UpdateModelFormMutation):
    class Meta:
        name = "TestApiUpdateThing"
        form_class = ThingForm


class Mutation(graphene.ObjectType):
    test_api_create_thing = CreateThing.Field()
    test_api_update_thing = UpdateThing.Field()


subschema = Subschema(mutation=Mutation)
