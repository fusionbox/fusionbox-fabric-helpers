from contextlib import contextmanager as _contextmanager

from fabric.api import prefix, env, local, cd, sudo


env.workon_home = '/var/python-environments'

env.tld = '.com'

__doc__ = """
TODO: Figure out a better way to construct these variables as to minimize the
number of environment variables that must be declared while still allowing for
highly detailed configuration.

Dev server
----------
project_directory - /var/www/{project_name}.{tld}/
virtual_env - /var/python-environments/{abbr}/bin/activate
vassals_file - /etc/vassals/{abbr}.ini

Production Server can have fundamentally different values for these.... (see webfaction)

Example env configs:
"""


@_contextmanager
def virtualenv(dir):
    """
    Context manager to run all commands under a specified python virtual env.
    """
    with prefix('source {workon_home}/{dir}/bin/activate'.format(dir=dir, **env)):
        yield


@_contextmanager
def project_directory():
    """
    Context manager to run all commands under a specified python virtual env.
    """
    with cd('/var/www/{project_name}{tld}'.format(**env)):
        yield


def files_changed(version, files):
    """
    Between version and HEAD, has anything in files changed?
    """
    if not version:
        return True
    if not isinstance(files, basestring):
        files = ' '.join(files)
    return "diff" in local("git diff {0} HEAD -- {1}".format(version, files), capture=True)


def supervisor_command(action, name):
    """
    Perform a command on a supervisor process.
    """
    sudo('supervisorctl {0} {1}'.format(action, name))
