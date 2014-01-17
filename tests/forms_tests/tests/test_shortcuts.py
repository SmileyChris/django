from __future__ import unicode_literals

from django import forms, http, shortcuts
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils.datastructures import MultiValueDict

request_factory = RequestFactory()


class Person(forms.Form):
    name = forms.CharField()


class FormsShortcutTests(TestCase):
    # Tests for form-related utils in the django/shortcuts.py module.

    def test_get_form_kwargs_GET(self):
        request = request_factory.get('/')
        self.assertEqual(shortcuts.get_form_kwargs(request), {})

    def test_get_form_kwargs_POST(self):
        from StringIO import StringIO
        test_file = StringIO('testdata')
        test_file.name = 'test'
        request = request_factory.post('/', data={'test': '1', 'f': test_file})
        result = shortcuts.get_form_kwargs(request)
        self.assertEqual(sorted(result.keys()), ['data', 'files'])
        self.assertEqual(result['data']['test'], '1')
        self.assertEqual(result['files']['f'].read(), 'testdata')

    def test_get_form_kwargs_PUT(self):
        request = request_factory.put('/', data='')
        self.assertEqual(
            shortcuts.get_form_kwargs(request),
            {'data': {}, 'files': {}})

    def test_get_form_kwargs_form_get(self):
        request = request_factory.get('/')
        form = Person(**shortcuts.get_form_kwargs(request))
        self.assertFalse(form.is_bound)
        self.assertFalse(form.is_valid())

    def test_get_form_kwargs_form_post_incomplete(self):
        request = request_factory.post('/', data={'test': '1'})
        form = Person(**shortcuts.get_form_kwargs(request))
        self.assertTrue(form.is_bound)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_get_form_kwargs_form_post_complete(self):
        request = request_factory.post('/', data={'name': 'Adrian'})
        form = Person(**shortcuts.get_form_kwargs(request))
        self.assertTrue(form.is_bound)
        self.assertTrue(form.is_valid())
