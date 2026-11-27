from django import template
from django.conf import settings

from accounts.demo import demo_label, demo_users

register = template.Library()


@register.inclusion_tag("accounts/_demo_login.html", takes_context=True)
def demo_login(context, kind):
    """Auswahl der Demo-Konten; ohne DEMO_LOGIN bleibt sie leer."""
    if not settings.DEMO_LOGIN:
        return {"enabled": False}
    options = [(user.pk, demo_label(user, kind)) for user in demo_users(kind)]
    return {
        "enabled": True,
        "kind": kind,
        "options": options,
        "next": context.get("next", ""),
        "csrf_token": context["csrf_token"],
    }
