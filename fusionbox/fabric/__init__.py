from fabric.api import env

from fusionbox.fabric.utils import Env

# Default fabric config
env.forward_agent = True
env.roledefs = {
    'dev': ['dev.fusionbox.com'],
    'live': [],
}

# Default fusionbox helper config
fb_env = Env()

fb_env.transport_method = 'git'

fb_env.web_home = '/var/www'
fb_env.workon_home = '/var/python-environments'

fb_env.tld = '.com'
