from __future__ import annotations

from doc_agent.charts.manager import ChartManager
from doc_agent.colors.manager import ColorManager
from doc_agent.smartart.manager import SmartArtManager
from doc_agent.templates.manager import TemplateManager
from doc_agent.users.manager import UserManager


def get_user_manager() -> UserManager:
    return UserManager()


def get_template_manager() -> TemplateManager:
    return TemplateManager()


def get_color_manager() -> ColorManager:
    return ColorManager()


def get_chart_manager() -> ChartManager:
    return ChartManager()


def get_smartart_manager() -> SmartArtManager:
    return SmartArtManager()
