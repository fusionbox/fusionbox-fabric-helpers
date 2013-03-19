from fabric.api import env

from fusionbox.fabric.config import Env

# Default fabric config
env.forward_agent = True
env.roledefs = {
    'dev': ['dev.fusionbox.com'],
    'live': [],
}

# Default fusionbox helper config
fb_env = Env()
