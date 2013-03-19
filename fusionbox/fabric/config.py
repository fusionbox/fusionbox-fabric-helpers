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
        # Global defaults
        'transport_method': 'git',
        'tld': '.com',

        'web_home': '/var/www',
        'workon_home': '/var/python-environments',
        'backups_dir': 'backups',
        'media_dir': 'media',

        'virtualenv': '{project_name}',
        'vassal': '{project_name}',

        # Dev defaults
        'dev_project_name': '{project_name}',
        'dev_tld': '{tld}',
        'dev_web_home': '{web_home}',
        'dev_virtualenv': '{virtualenv}',
        'dev_vassal': '{vassal}',
        'dev_workon_home': '{workon_home}',
        'dev_project_dir': '{dev_project_name}{dev_tld}',
        'dev_project_path': '{dev_web_home}/{dev_project_dir}',
        'dev_virtualenv_path': '{dev_workon_home}/{dev_virtualenv}',
        'dev_restart_cmd': 'sudo touch /etc/vassals/{dev_vassal}.ini',

        'dev_backups_dir': '{backups_dir}',
        'dev_media_dir': '{media_dir}',
        'dev_media_path': '{dev_project_path}/{dev_media_dir}',

        # Live defaults
        'live_project_name': '{project_name}',
        'live_tld': '{tld}',
        'live_web_home': '{web_home}',
        'live_virtualenv': '{virtualenv}',
        'live_vassal': '{vassal}',
        'live_workon_home': '{workon_home}',
        'live_project_dir': '{live_project_name}{live_tld}',
        'live_project_path': '{live_web_home}/{live_project_dir}',
        'live_virtualenv_path': '{live_workon_home}/{live_virtualenv}',
        'live_restart_cmd': 'sudo touch /etc/vassals/{live_vassal}.ini',

        'live_backups_dir': '{backups_dir}',
        'live_media_dir': '{media_dir}',
        'live_media_path': '{live_project_path}/{live_media_dir}',

        # Local defaults
        'local_backups_dir': '{backups_dir}',
        'local_media_dir': '{media_dir}',
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
