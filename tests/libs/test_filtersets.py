from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from libs.drf.filtersets.search import PhraseSearchFilter


class PhraseSearchFilterTest(TestCase):
    """Test cases for PhraseSearchFilter"""

    def setUp(self):
        """Set up test data"""
        self.factory = APIRequestFactory()

    def test_get_search_terms_returns_single_term(self):
        """Test that get_search_terms returns the query as a single term"""
        filter_instance = PhraseSearchFilter()
        django_request = self.factory.get("/test/", {"search": "John Doe"})
        request = Request(django_request)

        terms = filter_instance.get_search_terms(request)

        self.assertEqual(terms, ["John Doe"])

    def test_get_search_terms_empty_query(self):
        """Test that get_search_terms returns empty list for empty query"""
        filter_instance = PhraseSearchFilter()
        django_request = self.factory.get("/test/", {"search": ""})
        request = Request(django_request)

        terms = filter_instance.get_search_terms(request)

        self.assertEqual(terms, [])

    def test_get_search_terms_no_param(self):
        """Test that get_search_terms returns empty list when no search param"""
        filter_instance = PhraseSearchFilter()
        django_request = self.factory.get("/test/")
        request = Request(django_request)

        terms = filter_instance.get_search_terms(request)

        self.assertEqual(terms, [])
