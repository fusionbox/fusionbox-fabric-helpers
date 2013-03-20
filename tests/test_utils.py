from mock import patch
import unittest

from fusionbox.fabric.utils import virtualenv, supervisor_command


class VirtualenvTestCase(unittest.TestCase):
    def test_virtualenv_runs_commands_with_the_prefix_contextmanager(self):
        with patch('fusionbox.fabric.utils.prefix') as mock_prefix:
            with virtualenv('/var/virtualenvs/test'):
                pass

        mock_prefix.assert_called_with('source /var/virtualenvs/test/bin/activate')


class SupervisorCommandTestCase(unittest.TestCase):
    def test_supervisor_command_runs_a_remote_supervisorctl_command(self):
        with patch('fusionbox.fabric.utils.sudo') as mock_sudo:
            supervisor_command('stop', 'texting_and_driving')

        mock_sudo.assert_called_with('supervisorctl stop texting_and_driving')
