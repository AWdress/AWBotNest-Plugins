"""No standalone AI credentials or general SQL/service executor in the plugin."""


def load_page_agent_config(db=None):
    return {'enabled': False}
