from django import template
register = template.Library()

@register.simple_tag
def url_replace(request, field, value):
    """Replaces or adds a GET parameter to the current URL"""
    dict_ = request.GET.copy()
    dict_[field] = value
    return dict_.urlencode()
