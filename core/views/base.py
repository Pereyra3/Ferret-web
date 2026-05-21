"""Base class-based views (pattern aligned with tech_tool core/views/base.py)."""

from django.contrib.auth.mixins import LoginRequiredMixin

from core.views.mixins import DefaultStoreMixin, PageContextMixin


class BaseView(LoginRequiredMixin, DefaultStoreMixin, PageContextMixin):
    """Login required + default store + page shell context."""

    login_url = "login"
