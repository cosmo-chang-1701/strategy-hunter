from .database import get_session
from .state import app_state
from .services.option_chain_service import OptionChainService


# Dependency Injection: provide database session
get_db = get_session


# Dependency Injection: provide OptionChainService
def get_option_chain_service():
    is_live = bool(app_state.get("polygon_options_accessible", False))
    return OptionChainService(is_live=is_live)
