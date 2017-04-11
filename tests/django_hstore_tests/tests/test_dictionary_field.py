# -*- coding: utf-8 -*-
import datetime
import json
import pickle
import sys
from decimal import Decimal

from django import VERSION as DJANGO_VERSION
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models.aggregates import Count
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils.encoding import force_text

from django_hstore import get_version
from django_hstore.exceptions import HStoreDictException
from django_hstore.fields import HStoreDict
from django_hstore.forms import DictionaryFieldWidget
from django_hstore.utils import get_cast_for_param

from django_hstore_tests.models import (
    BadDefaultsModel,
    DataBag,
    DefaultsModel,
    NullableDataBag,
    NumberedDataBag,
    UniqueTogetherDataBag
)


class TestDictionaryField(TestCase):
    def setUp(self):
        DataBag.objects.all().delete()

    def _create_bags(self):
        alpha = DataBag.objects.create(name='alpha', data={'v': '1', 'v2': '3'})
        beta = DataBag.objects.create(name='beta', data={'v': '2', 'v2': '4'})
        return alpha, beta

    def _create_bitfield_bags(self):
        # create dictionaries with bits as dictionary keys (i.e. bag5 = {'b0':'1', 'b2':'1'})
        for i in range(10):
            DataBag.objects.create(name='bag%d' % (i,),
                                   data=dict(('b%d' % (bit,), '1') for bit in range(4) if (1 << bit) & i))

    def test_hstore_dict(self):
        alpha, beta = self._create_bags()
        self.assertEqual(alpha.data, {'v': '1', 'v2': '3'})
        self.assertEqual(beta.data, {'v': '2', 'v2': '4'})

    def test_decimal(self):
        databag = DataBag(name='decimal')
        databag.data['dec'] = Decimal('1.01')
        self.assertEqual(databag.data['dec'], force_text(Decimal('1.01')))

        databag.save()
        databag = DataBag.objects.get(name='decimal')
        self.assertEqual(databag.data['dec'], force_text(Decimal('1.01')))

        databag = DataBag(name='decimal', data={'dec': Decimal('1.01')})
        self.assertEqual(databag.data['dec'], force_text(Decimal('1.01')))

    def test_long(self):
        if sys.version < '3':
            l = long(100000000000)  # noqa
            databag = DataBag(name='long')
            databag.data['long'] = l
            self.assertEqual(databag.data['long'], force_text(l))

            databag.save()
            databag = DataBag.objects.get(name='long')
            self.assertEqual(databag.data['long'], force_text(l))

            databag = DataBag(name='long', data={'long': l})
            self.assertEqual(databag.data['long'], force_text(l))

    def test_number(self):
        databag = DataBag(name='number')
        databag.data['num'] = 1
        self.assertEqual(databag.data['num'], '1')

        databag.save()
        databag = DataBag.objects.get(name='number')
        self.assertEqual(databag.data['num'], '1')

        databag = DataBag(name='number', data={'num': 1})
        self.assertEqual(databag.data['num'], '1')

    def test_list(self):
        databag = DataBag.objects.create(name='list', data={'list': ['a', 'b', 'c']})
        databag = DataBag.objects.get(name='list')
        self.assertEqual(json.loads(databag.data['list']), ['a', 'b', 'c'])

    def test_dictionary(self):
        databag = DataBag.objects.create(name='dict', data={'dict': {'subkey': 'subvalue'}})
        databag = DataBag.objects.get(name='dict')
        self.assertEqual(json.loads(databag.data['dict']), {'subkey': 'subvalue'})

        databag.data['dict'] = {'subkey': True, 'list': ['a', 'b', False]}
        databag.save()
        self.assertEqual(json.loads(databag.data['dict']), {'subkey': True, 'list': ['a', 'b', False]})

    def test_boolean(self):
        databag = DataBag.objects.create(name='boolean', data={'boolean': True})
        databag = DataBag.objects.get(name='boolean')
        self.assertEqual(json.loads(databag.data['boolean']), True)

        self.assertTrue(DataBag.objects.get(data__contains={'boolean': True}))

    def test_is_pickable(self):
        m = DefaultsModel()
        m.save()
        try:
            pickle.dumps(m)
        except TypeError as e:
            self.fail('pickle of DefaultsModel failed: %s' % e)

    def test_empty_instantiation(self):
        bag = DataBag.objects.create(name='bag')
        self.assertTrue(isinstance(bag.data, dict))
        self.assertEqual(bag.data, {})

    def test_empty_querying(self):
        DataBag.objects.create(name='bag')
        self.assertTrue(DataBag.objects.get(data={}))
        self.assertTrue(DataBag.objects.filter(data={}))
        self.assertTrue(DataBag.objects.filter(data__contains={}))

    def test_nullable_queryinig(self):
        # backward incompatible change in 1.3.3:
        # default value of a dictionary field which is can be null will never be None
        # but always an empty HStoreDict
        NullableDataBag.objects.create(name='nullable')
        self.assertFalse(NullableDataBag.objects.filter(data__exact=None))
        self.assertFalse(NullableDataBag.objects.filter(data__isnull=True))
        self.assertTrue(NullableDataBag.objects.filter(data__isnull=False))

    def test_nullable_set(self):
        n = NullableDataBag()
        n.data['test'] = 'test'
        self.assertEqual(n.data['test'], 'test')

    def test_nullable_get(self):
        n = NullableDataBag()
        self.assertEqual(n.data.get('test', 'test'), 'test')
        self.assertEqual(n.data.get('test', False), False)
        self.assertEqual(n.data.get('test'), None)

    def test_nullable_getitem(self):
        n = NullableDataBag()
        with self.assertRaises(KeyError):
            n.data['test']

    def test_null_values(self):
        null_v = DataBag.objects.create(name="test", data={"v": None})
        nonnull_v = DataBag.objects.create(name="test", data={"v": "item"})

        r = DataBag.objects.filter(data__isnull={"v": True})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], null_v)

        r = DataBag.objects.filter(data__isnull={"v": False})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], nonnull_v)

    def test_named_querying(self):
        alpha, beta = self._create_bags()
        self.assertEqual(DataBag.objects.get(name='alpha'), alpha)
        self.assertEqual(DataBag.objects.filter(name='beta')[0], beta)

    def test_aggregates(self):
        self._create_bitfield_bags()
        self.assertEqual(DataBag.objects.filter(data__contains={'b0': '1'}).aggregate(Count('id'))['id__count'], 5)
        self.assertEqual(DataBag.objects.filter(data__contains={'b1': '1'}).aggregate(Count('id'))['id__count'], 4)

    def test_annotations(self):
        self._create_bitfield_bags()

        self.assertEqual(DataBag.objects.annotate(num_id=Count('id')).filter(num_id=1)[0].num_id, 1)

    def test_nested_filtering(self):
        self._create_bitfield_bags()

        # Test cumulative successive filters for both dictionaries and other fields
        f = DataBag.objects.all()
        self.assertEqual(10, f.count())
        f = f.filter(data__contains={'b0': '1'})
        self.assertEqual(5, f.count())
        f = f.filter(data__contains={'b1': '1'})
        self.assertEqual(2, f.count())
        f = f.filter(name='bag3')
        self.assertEqual(1, f.count())

    def test_unicode_processing(self):
        greets = {
            u'de': u'Gr\xfc\xdfe, Welt',
            u'en': u'hello, world',
            u'es': u'hola, ma\xf1ana',
            u'he': u'\u05e9\u05dc\u05d5\u05dd, \u05e2\u05d5\u05dc\u05dd',
            u'jp': u'\u3053\u3093\u306b\u3061\u306f\u3001\u4e16\u754c',
            u'zh': u'\u4f60\u597d\uff0c\u4e16\u754c',
        }
        DataBag.objects.create(name='multilang', data=greets)
        self.assertEqual(greets, DataBag.objects.get(name='multilang').data)

    def test_query_escaping(self):
        me = self

        def readwrite(s):
            # try create and query with potentially illegal characters in the field and dictionary key/value
            o = DataBag.objects.create(name=s, data={s: s})
            me.assertEqual(o, DataBag.objects.get(name=s, data={s: s}))
        readwrite('\' select')
        readwrite('% select')
        readwrite('\\\' select')
        readwrite('-- select')
        readwrite('\n select')
        readwrite('\r select')
        readwrite('* select')

    def test_replace_full_dictionary(self):
        DataBag.objects.create(name='foo', data={'change': 'old value', 'remove': 'baz'})

        replacement = {'change': 'new value', 'added': 'new'}
        DataBag.objects.filter(name='foo').update(data=replacement)
        self.assertEqual(replacement, DataBag.objects.get(name='foo').data)

    def test_equivalence_querying(self):
        alpha, beta = self._create_bags()
        for bag in (alpha, beta):
            data = {'v': bag.data['v'], 'v2': bag.data['v2']}
            self.assertEqual(DataBag.objects.get(data=data), bag)
            r = DataBag.objects.filter(data=data)
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0], bag)

    def test_key_value_subset_querying(self):
        alpha, beta = self._create_bags()
        for bag in (alpha, beta):
            r = DataBag.objects.filter(data__contains={'v': bag.data['v']})
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0], bag)
            r = DataBag.objects.filter(data__contains={'v': bag.data['v'], 'v2': bag.data['v2']})
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0], bag)

    def test_value_in_subset_querying(self):
        alpha, beta = self._create_bags()
        res = DataBag.objects.filter(data__contains={'v': [alpha.data['v']]})
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], alpha)
        res = DataBag.objects.filter(data__contains={'v': [alpha.data['v'], beta.data['v']]})
        self.assertEqual(len(res), 2)
        self.assertEqual(set(res), set([alpha, beta]))

        # int values are ok
        r = DataBag.objects.filter(data__contains={'v': [int(alpha.data['v'])]})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], alpha)

    def test_key_value_gt_querying(self):
        alpha, beta = self._create_bags()
        self.assertGreater(beta.data['v'], alpha.data['v'])
        r = DataBag.objects.filter(data__gt={'v': alpha.data['v']})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], beta)
        r = DataBag.objects.filter(data__gte={'v': alpha.data['v']})
        self.assertEqual(len(r), 2)

    def test_key_value_gt_casting_number_query(self):
        alpha = DataBag.objects.create(name='alpha', data={'v': 10})
        DataBag.objects.create(name='alpha', data={'v': 1})

        r = DataBag.objects.filter(data__gt={'v': 2})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], alpha)

    def test_key_value_contains_casting_date_query(self):
        date = datetime.date(2014, 9, 28)
        alpha = DataBag.objects.create(name='alpha', data={'v': date.isoformat()})

        r = DataBag.objects.filter(data__contains={'v': date})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], alpha)

    def test_multiple_key_value_gt_querying(self):
        alpha, beta = self._create_bags()
        self.assertGreater(beta.data['v'], alpha.data['v'])
        r = DataBag.objects.filter(data__gt={'v': alpha.data['v'], 'v2': alpha.data['v2']})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], beta)
        r = DataBag.objects.filter(data__gt={'v': alpha.data['v'], 'v2': beta.data['v2']})
        self.assertEqual(len(r), 0)
        r = DataBag.objects.filter(data__gte={'v': alpha.data['v'], 'v2': alpha.data['v2']})
        self.assertEqual(len(r), 2)
        r = DataBag.objects.filter(data__gte={'v': alpha.data['v'], 'v2': beta.data['v2']})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], beta)

    def test_multiple_key_value_lt_querying(self):
        alpha, beta = self._create_bags()
        self.assertGreater(beta.data['v'], alpha.data['v'])
        r = DataBag.objects.filter(data__lt={'v': beta.data['v'], 'v2': beta.data['v2']})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], alpha)
        r = DataBag.objects.filter(data__lt={'v': beta.data['v'], 'v2': alpha.data['v2']})
        self.assertEqual(len(r), 0)
        r = DataBag.objects.filter(data__lte={'v': beta.data['v'], 'v2': beta.data['v2']})
        self.assertEqual(len(r), 2)
        r = DataBag.objects.filter(data__lte={'v': beta.data['v'], 'v2': alpha.data['v2']})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], alpha)

    def test_key_value_lt_querying(self):
        alpha, beta = self._create_bags()
        self.assertLess(alpha.data['v'], beta.data['v'])
        r = DataBag.objects.filter(data__lt={'v': beta.data['v']})
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0], alpha)
        r = DataBag.objects.filter(data__lte={'v': beta.data['v']})
        self.assertEqual(len(r), 2)

    def test_multiple_key_subset_querying(self):
        alpha, beta = self._create_bags()
        for keys in (['v'], ['v', 'v2']):
            self.assertEqual(DataBag.objects.filter(data__contains=keys).count(), 2)
        for keys in (['v', 'nv'], ['n1', 'n2']):
            self.assertEqual(DataBag.objects.filter(data__contains=keys).count(), 0)

    def test_single_key_querying(self):
        alpha, beta = self._create_bags()
        for key in ('v', 'v2'):
            self.assertEqual(DataBag.objects.filter(data__contains=[key]).count(), 2)
        for key in ('n1', 'n2'):
            self.assertEqual(DataBag.objects.filter(data__contains=[key]).count(), 0)

    def test_simple_text_icontains_querying(self):
        alpha, beta = self._create_bags()
        DataBag.objects.create(name='gamma', data={'theKey': 'someverySpecialValue', 'v2': '3'})

        self.assertEqual(DataBag.objects.filter(data__contains='very').count(), 1)
        self.assertEqual(DataBag.objects.filter(data__contains='very')[0].name, 'gamma')
        self.assertEqual(DataBag.objects.filter(data__icontains='specialvalue').count(), 1)
        self.assertEqual(DataBag.objects.filter(data__icontains='specialvalue')[0].name, 'gamma')

        self.assertEqual(DataBag.objects.filter(data__contains='the').count(), 1)
        self.assertEqual(DataBag.objects.filter(data__contains='the')[0].name, 'gamma')
        self.assertEqual(DataBag.objects.filter(data__icontains='eke').count(), 1)
        self.assertEqual(DataBag.objects.filter(data__icontains='eke')[0].name, 'gamma')

    def test_invalid_containment_lookup_values(self):
        alpha, beta = self._create_bags()
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__contains=99)[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__icontains=99)[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__icontains=[])[0]

    def test_invalid_comparison_lookup_values(self):
        alpha, beta = self._create_bags()
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__lt=[1, 2])[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__lt=99)[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__lte=[1, 2])[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__lte=99)[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__gt=[1, 2])[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__gt=99)[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__gte=[1, 2])[0]
        with self.assertRaises(ValueError):
            DataBag.objects.filter(data__gte=99)[0]

    def test_hkeys(self):
        alpha, beta = self._create_bags()
        self.assertEqual(DataBag.objects.hkeys(id=alpha.id, attr='data'), ['v', 'v2'])
        self.assertEqual(DataBag.objects.hkeys(id=beta.id, attr='data'), ['v', 'v2'])

    def test_hpeek(self):
        alpha, beta = self._create_bags()
        self.assertEqual(DataBag.objects.hpeek(id=alpha.id, attr='data', key='v'), '1')
        self.assertEqual(DataBag.objects.filter(id=alpha.id).hpeek(attr='data', key='v'), '1')
        self.assertEqual(DataBag.objects.hpeek(id=alpha.id, attr='data', key='invalid'), None)

    def test_hremove(self):
        alpha, beta = self._create_bags()
        self.assertEqual(DataBag.objects.get(name='alpha').data, alpha.data)
        DataBag.objects.filter(name='alpha').hremove('data', 'v2')
        self.assertEqual(DataBag.objects.get(name='alpha').data, {'v': '1'})

        self.assertEqual(DataBag.objects.get(name='beta').data, beta.data)
        DataBag.objects.filter(name='beta').hremove('data', ['v', 'v2'])
        self.assertEqual(DataBag.objects.get(name='beta').data, {})

    def test_hslice(self):
        alpha, beta = self._create_bags()
        self.assertEqual(DataBag.objects.hslice(id=alpha.id, attr='data', keys=['v']), {'v': '1'})
        self.assertEqual(DataBag.objects.filter(id=alpha.id).hslice(attr='data', keys=['v']), {'v': '1'})
        self.assertEqual(DataBag.objects.hslice(id=alpha.id, attr='data', keys=['ggg']), {})

    def test_hupdate(self):
        alpha, beta = self._create_bags()
        self.assertEqual(DataBag.objects.get(name='alpha').data, alpha.data)
        DataBag.objects.filter(name='alpha').hupdate('data', {'v2': '10', 'v3': '20'})
        self.assertEqual(DataBag.objects.get(name='alpha').data, {'v': '1', 'v2': '10', 'v3': '20'})

    def test_hupdate_atomic(self):
        """ https://github.com/djangonauts/django-hstore/issues/84 """
        if hasattr(transaction, 'atomic'):
            with transaction.atomic():
                self.test_hupdate()

    def test_default(self):
        m = DefaultsModel()
        m.save()

    def test_bad_default(self):
        m = BadDefaultsModel()
        try:
            m.save()
        except IntegrityError:
            if DJANGO_VERSION[:2] >= (1, 6):
                pass
            # TODO: remove in future versions of django-hstore
            else:
                transaction.rollback()
        else:
            self.assertTrue(False)

    def test_serialization_deserialization(self):
        alpha, beta = self._create_bags()
        self.assertEqual(json.loads(str(DataBag.objects.get(name='alpha').data)), json.loads(str(alpha.data)))
        self.assertEqual(json.loads(str(DataBag.objects.get(name='beta').data)), json.loads(str(beta.data)))

    def test_hstoredictionaryexception(self):
        # ok
        HStoreDict({})

        # json object string allowed
        HStoreDict('{}')

        # None is ok, will be converted to empty dict
        HStoreDict(None)
        HStoreDict()

        # non-json string not allowed
        with self.assertRaises(HStoreDictException):
            HStoreDict('wrong')

        # list not allowed
        with self.assertRaises(HStoreDictException):
            HStoreDict(['wrong'])

        # json array string representation not allowed
        with self.assertRaises(HStoreDictException):
            HStoreDict('["wrong"]')

        # number not allowed
        with self.assertRaises(HStoreDictException):
            HStoreDict(3)

    def test_hstoredictionary_unicode_vs_str(self):
        d = HStoreDict({'test': 'test'})
        self.assertEqual(d.__str__(), d.__unicode__())

    def test_hstore_model_field_validation(self):
        d = DataBag()

        with self.assertRaises(ValidationError):
            d.full_clean()

        d.data = 'test'

        with self.assertRaises(ValidationError):
            d.full_clean()

        d.data = '["test"]'

        with self.assertRaises(ValidationError):
            d.full_clean()

        d.data = ["test"]

        with self.assertRaises(ValidationError):
            d.full_clean()

        d.data = {
            'a': 1,
            'b': 2.2,
            'c': ['a', 'b'],
            'd': {'test': 'test'}
        }

        with self.assertRaises(ValidationError):
            d.full_clean()

    def test_admin_widget(self):
        alpha, beta = self._create_bags()

        # create admin user
        admin = User.objects.create(username='admin', password='tester', is_staff=True, is_superuser=True, is_active=True)
        admin.set_password('tester')
        admin.save()
        # login as admin
        self.client.login(username='admin', password='tester')

        # access admin change form page
        url = reverse('admin:django_hstore_tests_databag_change', args=[alpha.id])
        response = self.client.get(url)
        # ensure textarea with id="id_data" is there
        self.assertContains(response, 'textarea')
        self.assertContains(response, 'id_data')

    def test_dictionary_default_admin_widget(self):
        class HForm(forms.ModelForm):
            class Meta:
                model = DataBag
                exclude = []

        form = HForm()
        self.assertEqual(form.fields['data'].widget.__class__, DictionaryFieldWidget)

    def test_dictionary_custom_admin_widget(self):
        class CustomWidget(forms.Widget):
            pass

        class HForm(forms.ModelForm):
            class Meta:
                model = DataBag
                widgets = {'data': CustomWidget}
                exclude = []

        form = HForm()
        self.assertEqual(form.fields['data'].widget.__class__, CustomWidget)

    def test_get_version(self):
        get_version()

    def test_unique_together(self):
        d = UniqueTogetherDataBag()
        d.name = 'test'
        d.data = {'test': 'test '}
        d.full_clean()
        d.save()

        d = UniqueTogetherDataBag()
        d.name = 'test'
        d.data = {'test': 'test '}
        with self.assertRaises(ValidationError):
            d.full_clean()

    def test_properties_hstore(self):
        """
        Make sure the hstore field does what it is supposed to.
        """
        from django_hstore.fields import HStoreDict

        instance = DataBag()
        test_props = {'foo': 'bar', 'size': '3'}

        instance.name = 'foo'
        instance.data = test_props
        instance.save()

        self.assertEqual(type(instance.data), HStoreDict)
        self.assertEqual(instance.data, test_props)
        instance = DataBag.objects.get(pk=instance.pk)

        self.assertEqual(type(instance.data), HStoreDict)

        self.assertEqual(instance.data, test_props)
        self.assertEqual(instance.data['size'], '3')
        self.assertIn('foo', instance.data)

    def test_unicode(self):
        i = DataBag()
        i.data['key'] = 'è'
        i.save()

        i.data['key'] = u'è'
        i.save()

    def test_get_default(self):
        d = HStoreDict()
        self.assertIsNone(d.get('none_key', None))
        self.assertIsNone(d.get('none_key'))

    def test_str(self):
        d = DataBag()
        self.assertEqual(str(d.data), '{}')

    def test_array_with_decimal(self):
        instance = DataBag(name="decimal")
        array_decimal = [Decimal('1.01')]
        array_dumped = '[1.01]'
        instance.data['arr_dec'] = array_decimal

        self.assertEqual(instance.data['arr_dec'], array_dumped)
        instance.save()

        instance = DataBag.objects.get(pk=instance.pk)
        self.assertEqual(instance.data['arr_dec'], array_dumped)

    def test_native_contains(self):
        d = DataBag()
        d.name = "A bag of data"
        d.data = {
            'd1': '1',
            'd2': '2'
        }
        d.save()
        result = DataBag.objects.filter(name__contains='of data')
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].pk, d.pk)
        result = DataBag.objects.filter(name__contains='OF data')
        self.assertEqual(result.count(), 0)

    def test_native_icontains(self):
        d = DataBag()
        d.name = "A bag of data"
        d.data = {
            'd1': '1',
            'd2': '2'
        }
        d.save()
        result = DataBag.objects.filter(name__icontains='A bAg')
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].pk, d.pk)

    def test_native_gt(self):
        d = NumberedDataBag()
        d.name = "A bag of data"
        d.number = 12
        d.save()
        result = NumberedDataBag.objects.filter(number__gt=12)
        self.assertEqual(result.count(), 0)
        result = NumberedDataBag.objects.filter(number__gt=1)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].pk, d.pk)
        result = NumberedDataBag.objects.filter(number__gt=13)
        self.assertEqual(result.count(), 0)

    def test_native_gte(self):
        d = NumberedDataBag()
        d.name = "A bag of data"
        d.number = 12
        d.save()
        result = NumberedDataBag.objects.filter(number__gte=12)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].pk, d.pk)
        result = NumberedDataBag.objects.filter(number__gte=1)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].pk, d.pk)
        result = NumberedDataBag.objects.filter(number__gte=13)
        self.assertEqual(result.count(), 0)

    def test_native_lt(self):
        d = NumberedDataBag()
        d.name = "A bag of data"
        d.number = 12
        d.save()
        result = NumberedDataBag.objects.filter(number__lt=20)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].pk, d.pk)
        result = NumberedDataBag.objects.filter(number__lt=12)
        self.assertEqual(result.count(), 0)
        result = NumberedDataBag.objects.filter(number__lt=1)
        self.assertEqual(result.count(), 0)

    def test_native_lte(self):
        d = NumberedDataBag()
        d.name = "A bag of data"
        d.number = 12
        d.save()
        result = NumberedDataBag.objects.filter(number__lte=12)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].pk, d.pk)
        result = NumberedDataBag.objects.filter(number__lte=13)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].pk, d.pk)
        result = NumberedDataBag.objects.filter(number__lte=1)
        self.assertEqual(result.count(), 0)

    def test_get_cast_for_param(self):
        self.assertEqual(get_cast_for_param([], 'a'), '')
        self.assertEqual(get_cast_for_param({'a': True}, 'a'), '::boolean')
        self.assertEqual(get_cast_for_param({'a': datetime.datetime}, 'a'), '::timestamp')
        self.assertEqual(get_cast_for_param({'a': datetime.time}, 'a'), '::time')
        self.assertEqual(get_cast_for_param({'a': int}, 'a'), '::bigint')
        self.assertEqual(get_cast_for_param({'a': float}, 'a'), '::float8')
        from decimal import Decimal
        self.assertEqual(get_cast_for_param({'a': Decimal}, 'a'), '::numeric')
