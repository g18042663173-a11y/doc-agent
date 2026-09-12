from doc_agent.api.aicoding import router as aicoding_router
from doc_agent.api.charts import router as charts_router
from doc_agent.api.colors import router as colors_router
from doc_agent.api.generate import router as generate_router
from doc_agent.api.profiles import router as profiles_router
from doc_agent.api.smartart import router as smartart_router
from doc_agent.api.system import router as system_router
from doc_agent.api.templates import router as templates_router
from doc_agent.api.users import router as users_router

__all__ = [
    "charts_router",
    "aicoding_router",
    "colors_router",
    "generate_router",
    "profiles_router",
    "smartart_router",
    "system_router",
    "templates_router",
    "users_router",
]
