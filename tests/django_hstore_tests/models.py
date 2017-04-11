import django
from django.db import models

from django_hstore import hstore
from django_hstore.apps import GEODJANGO_INSTALLED

__all__ = [
    'Ref',
    'DataBag',
    'SerializedDataBag',
    'SerializedDataBagNoID',
    'NullableDataBag',
    'RefsBag',
    'NullableRefsBag',
    'DefaultsModel',
    'BadDefaultsModel',
    'DefaultsInline',
    'NumberedDataBag',
    'UniqueTogetherDataBag'
]


class Ref(models.Model):
    name = models.CharField(max_length=32)


class HStoreModel(models.Model):
    objects = hstore.HStoreManager()

    class Meta:
        abstract = True


class DataBag(HStoreModel):
    name = models.CharField(max_length=32)
    data = hstore.DictionaryField()


class SerializedDataBag(HStoreModel):
    name = models.CharField(max_length=32)
    data = hstore.SerializedDictionaryField()


class SerializedDataBagNoID(HStoreModel):
    slug = models.SlugField(primary_key=True)
    name = models.CharField(max_length=32)
    data = hstore.SerializedDictionaryField()


class NullableDataBag(HStoreModel):
    name = models.CharField(max_length=32)
    data = hstore.DictionaryField(null=True)


class RefsBag(HStoreModel):
    name = models.CharField(max_length=32)
    refs = hstore.ReferencesField()


class NullableRefsBag(HStoreModel):
    name = models.CharField(max_length=32)
    refs = hstore.ReferencesField(null=True, blank=True)


class DefaultsModel(models.Model):
    a = hstore.DictionaryField(default={})
    b = hstore.DictionaryField(default=None, null=True)
    c = hstore.DictionaryField(default={'x': '1'})


class BadDefaultsModel(models.Model):
    a = hstore.DictionaryField(default=None)


class DefaultsInline(models.Model):
    parent = models.ForeignKey(DefaultsModel)
    d = hstore.DictionaryField(default={'default': 'yes'})


class NumberedDataBag(HStoreModel):
    name = models.CharField(max_length=32)
    data = hstore.DictionaryField()
    number = models.IntegerField()


class UniqueTogetherDataBag(HStoreModel):
    name = models.CharField(max_length=32)
    data = hstore.DictionaryField()

    class Meta:
        unique_together = ('name', 'data')

if django.VERSION >= (1, 6):
    class SchemaDataBag(HStoreModel):
        name = models.CharField(max_length=32)
        data = hstore.DictionaryField(schema=[
            {
                'name': 'number',
                'class': 'IntegerField',
                'kwargs': {
                    'default': 0
                }
            },
            {
                'name': 'float',
                'class': models.FloatField,
                'kwargs': {
                    'default': 1.0
                }
            },
            {
                'name': 'boolean',
                'class': 'BooleanField',
            },
            {
                'name': 'boolean_true',
                'class': 'BooleanField',
                'kwargs': {
                    'verbose_name': 'boolean true',
                    'default': True
                }
            },
            {
                'name': 'char',
                'class': 'CharField',
                'kwargs': {
                    'default': 'test', 'blank': True, 'max_length': 10
                }
            },
            {
                'name': 'text',
                'class': 'TextField',
                'kwargs': {
                    'blank': True
                }
            },
            {
                'name': 'choice',
                'class': 'CharField',
                'kwargs': {
                    'blank': True,
                    'max_length': 10,
                    'choices': (('choice1', 'choice1'), ('choice2', 'choice2')),
                    'default': 'choice1'
                }
            },
            {
                'name': 'choice2',
                'class': 'CharField',
                'kwargs': {
                    'blank': True,
                    'max_length': 10,
                    'choices': (('choice1', 'choice1'), ('choice2', 'choice2')),
                }
            },
            {
                'name': 'date',
                'class': 'DateField',
                'kwargs': {
                    'blank': True
                }
            },
            {
                'name': 'datetime',
                'class': 'DateTimeField',
                'kwargs': {
                    'blank': True,
                    'null': True
                }
            },
            {
                'name': 'decimal',
                'class': 'DecimalField',
                'kwargs': {
                    'blank': True,
                    'decimal_places': 2,
                    'max_digits': 4
                }
            },
            {
                'name': 'email',
                'class': 'EmailField',
                'kwargs': {
                    'blank': True
                }
            },
            {
                'name': 'ip',
                'class': 'GenericIPAddressField',
                'kwargs': {
                    'blank': True,
                    'null': True
                }
            },
            {
                'name': 'url',
                'class': models.URLField,
                'kwargs': {
                    'blank': True
                }
            },
        ])

    class NullSchemaDataBag(HStoreModel):
        name = models.CharField(max_length=32)
        data = hstore.DictionaryField(null=True, default=None, schema=[
            {
                'name': 'number',
                'class': 'IntegerField',
                'kwargs': {
                    'default': 1
                }
            },
            {
                'name': 'char',
                'class': 'CharField',
                'kwargs': {
                    'default': 'test', 'blank': True, 'max_length': 10
                }
            }
        ])

    __all__.append('SchemaDataBag')
    __all__.append('NullSchemaDataBag')


# if geodjango is in use define Location model, which contains GIS data
if GEODJANGO_INSTALLED:
    from django.contrib.gis.db import models as geo_models

    class Location(geo_models.Model):
        name = geo_models.CharField(max_length=32)
        data = hstore.DictionaryField()
        point = geo_models.GeometryField()

        objects = hstore.HStoreGeoManager()

    __all__.append('Location')
