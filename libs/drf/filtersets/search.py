from rest_framework.filters import SearchFilter


class PhraseSearchFilter(SearchFilter):
    """
    Search filter that treats the entire search query as a single phrase,
    rather than splitting it into individual terms.
    """

    def get_search_terms(self, request):
        """
        Return the search query as a single term instead of splitting into words.
        """
        params = request.query_params.get(self.search_param, "")
        return [params] if params else []
