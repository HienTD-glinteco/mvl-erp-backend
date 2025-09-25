from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """
    Renderer that wraps all responses in a standardized envelope format.
    Success responses: {"success": true, "data": {...}, "error": null}
    Error responses: {"success": false, "data": null, "error": {...}}
    """
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        resp = renderer_context["response"]
        is_error = resp.exception
        envelope = {
            "success": not is_error,
            "data": None if is_error else data,
            "error": data if is_error else None
        }
        return super().render(envelope, accepted_media_type, renderer_context)
