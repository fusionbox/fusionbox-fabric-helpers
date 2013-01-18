from contextlib import contextmanager as _contextmanager
from string import Formatter

from fabric.api import local, prefix, sudo


class Env(object):
    """
    Stores config settings for fusionbox fabric helper routines.  Dynamically
    builds the value of certain properties unless their value was manually set.

    NOTE:
    Be careful not to define properties that reference each other...will cause
    a stack overflow.
    """
    DEFAULTS = {
        # Global defaults
        'virtualenv': '{project_name}',
        'vassal': '{project_name}',

        # Dev-specific defaults
        'dev_project_name': '{project_name}',
        'dev_tld': '{tld}',
        'dev_web_home': '{web_home}',
        'dev_virtualenv': '{virtualenv}',
        'dev_vassal': '{vassal}',
        'dev_workon_home': '{workon_home}',
        'dev_project_dir': '{dev_project_name}{dev_tld}',
        'dev_project_loc': '{dev_web_home}/{dev_project_dir}',
        'dev_virtualenv_loc': '{dev_workon_home}/{dev_virtualenv}',
        'dev_restart_cmd': 'sudo touch /etc/vassals/{dev_vassal}.ini',

        # Live-specific defaults
        'live_project_name': '{project_name}',
        'live_tld': '{tld}',
        'live_web_home': '{web_home}',
        'live_virtualenv': '{virtualenv}',
        'live_vassal': '{vassal}',
        'live_workon_home': '{workon_home}',
        'live_project_dir': '{live_project_name}{live_tld}',
        'live_project_loc': '{live_web_home}/{live_project_dir}',
        'live_virtualenv_loc': '{live_workon_home}/{live_virtualenv}',
        'live_restart_cmd': 'sudo touch /etc/vassals/{live_vassal}.ini',
    }

    def __init__(self):
        self._formatter = Formatter()

    def __getattr__(self, name):
        if name in self.DEFAULTS:
            # If there is a default value format, build the default value
            return self._format(self.DEFAULTS[name])
        else:
            raise AttributeError("'{0}' object has no attribute '{1}'".format(
                type(self).__name__,
                name,
            ))

    def __getitem__(self, key):
        return getattr(self, key)

    def _format(self, f):
        # Use a string formatter instance so we can use any object that defines
        # __getitem__
        return self._formatter.vformat(f, None, self)

    def role(self, role, name):
        return getattr(self, role + '_' + name)


@_contextmanager
def virtualenv(dir):
    """
    Context manager to run all commands under the python virtual env at ``dir``.
    """
    with prefix('source {0}/bin/activate'.format(dir)):
        yield


def files_changed(version, files):
    """
    Checks if anything in ``files`` has changed between version and local HEAD.
    """
    if not version:
        return True
    if not isinstance(files, basestring):
        files = ' '.join(files)
    return "diff" in local("git diff {0} HEAD -- {1}".format(version, files), capture=True)


def supervisor_command(action, name):
    """
    Performs a command on a supervisor process.
    """
    sudo('supervisorctl {0} {1}'.format(action, name))
