from string import Formatter


class Env(object):
    """
    Stores config settings for fusionbox fabric helper routines.  Dynamically
    builds the value of certain properties unless their value was manually set.

    NOTE:
    Be careful not to define properties that reference each other...will cause
    a stack overflow.
    """
    DEFAULTS = {
        # Dev-specific defaults
        'dev_project_name': '{project_name}',
        'dev_tld': '{tld}',
        'dev_web_home': '{web_home}',
        'dev_virtualenv': '{virtualenv}',
        'dev_workon_home': '{workon_home}',
        'dev_project_dir': '{dev_project_name}{dev_tld}',
        'dev_project_loc': '{dev_web_home}/{dev_project_dir}',
        'dev_virtualenv_loc': '{dev_workon_home}/{dev_virtualenv}',

        # Live-specific defaults
        'live_project_name': '{project_name}',
        'live_tld': '{tld}',
        'live_web_home': '{web_home}',
        'live_virtualenv': '{virtualenv}',
        'live_workon_home': '{workon_home}',
        'live_project_dir': '{live_project_name}{live_tld}',
        'live_project_loc': '{live_web_home}/{live_project_dir}',
        'live_virtualenv_loc': '{live_workon_home}/{live_virtualenv}',
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
        return self._formatter.vformat(f, None, self)
