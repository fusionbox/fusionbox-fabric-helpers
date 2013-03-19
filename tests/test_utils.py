from copy import copy
import unittest

from fusionbox.fabric.utils import Env


class EnvTestCase(unittest.TestCase):
    def setUp(self):
        self.empty_env = Env()

        self.env = Env()
        self.env.project_name = 'sammich'

        self.defaults = {
            'transport_method': 'git',
            'tld': '.com',

            'web_home': '/var/www',
            'workon_home': '/var/python-environments',
            'backups_dir': 'backups',
            'media_dir': 'media',

            'virtualenv': 'sammich',
            'vassal': 'sammich',

            'dev_project_name': 'sammich',
            'dev_tld': '.com',
            'dev_web_home': '/var/www',
            'dev_virtualenv': 'sammich',
            'dev_vassal': 'sammich',
            'dev_workon_home': '/var/python-environments',
            'dev_project_dir': 'sammich.com',
            'dev_project_loc': '/var/www/sammich.com',
            'dev_virtualenv_loc': '/var/python-environments/sammich',
            'dev_restart_cmd': 'sudo touch /etc/vassals/sammich.ini',

            'dev_backups_dir': 'backups',
            'dev_media_dir': 'media',
            'dev_media_loc': '/var/www/sammich.com/media',

            'live_project_name': 'sammich',
            'live_tld': '.com',
            'live_web_home': '/var/www',
            'live_virtualenv': 'sammich',
            'live_vassal': 'sammich',
            'live_workon_home': '/var/python-environments',
            'live_project_dir': 'sammich.com',
            'live_project_loc': '/var/www/sammich.com',
            'live_virtualenv_loc': '/var/python-environments/sammich',
            'live_restart_cmd': 'sudo touch /etc/vassals/sammich.ini',

            'live_backups_dir': 'backups',
            'live_media_dir': 'media',
            'live_media_loc': '/var/www/sammich.com/media',

            'local_backups_dir': 'backups',
            'local_media_dir': 'media',
        }

    def test_env_has_default_values(self):
        self.assertEqual(self.empty_env.backups_dir, 'backups')
        self.assertEqual(self.empty_env.media_dir, 'media')

    def test_env_has_no_default_project_name(self):
        self.assertRaises(
            AttributeError,
            lambda: self.empty_env.project_name,
        )

    def test_env_builds_default_values_based_on_other_values(self):
        for k, v in self.defaults.iteritems():
            self.assertEqual(getattr(self.env, k), v)

    def test_default_values_can_be_overridden_by_manually_setting_an_attribute(self):
        self.env.dev_virtualenv = 'wrap'
        self.env.dev_vassal = 'sandwich'

        self.env.live_tld = '.net'
        self.env.live_web_home = '/home/mctest/webapps/sammich'
        self.env.live_workon_home = '/home/mctest/virtualenvs'
        self.env.live_restart_cmd = '/home/mctest/webapps/sammich/apache2/bin/restart'

        self.defaults.update({
            'dev_virtualenv': 'wrap',
            'dev_vassal': 'sandwich',
            'dev_virtualenv_loc': '/var/python-environments/wrap',
            'dev_restart_cmd': 'sudo touch /etc/vassals/sandwich.ini',

            'live_tld': '.net',
            'live_web_home': '/home/mctest/webapps/sammich',
            'live_workon_home': '/home/mctest/virtualenvs',
            'live_project_dir': 'sammich.net',
            'live_project_loc': '/home/mctest/webapps/sammich/sammich.net',
            'live_virtualenv_loc': '/home/mctest/virtualenvs/sammich',
            'live_restart_cmd': '/home/mctest/webapps/sammich/apache2/bin/restart',

            'live_media_loc': '/home/mctest/webapps/sammich/sammich.net/media',
        })

        for k, v in self.defaults.iteritems():
            self.assertEqual(getattr(self.env, k), v)

    def test_default_values_that_reference_each_other_cause_stack_overflow(self):
        class CircularEnv(Env):
            DEFAULTS = copy(Env.DEFAULTS)
            DEFAULTS['ouroboros_head'] = '{ouroboros_tail}'
            DEFAULTS['ouroboros_tail'] = '{ouroboros_head}'

        ouroboros = CircularEnv()

        self.assertRaises(RuntimeError, lambda: ouroboros.ouroboros_head)

    def test_role_looks_up_attributes_with_a_certain_prefix(self):
        self.env.dev_vassal = 'sandwich'
        self.env.live_tld = '.net'

        self.assertEqual(self.env.role('dev', 'vassal'), 'sandwich')
        self.assertEqual(self.env.role('live', 'tld'), '.net')
        self.assertEqual(self.env.role('local', 'backups_dir'), 'backups')
