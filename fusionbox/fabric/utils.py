from contextlib import contextmanager as _contextmanager

import fabric


@_contextmanager
def virtualenv(dir):
    """
    Context manager to run all commands under the python virtual env at ``dir``.
    """
    with fabric.api.prefix('source {0}/bin/activate'.format(dir)):
        yield


def files_changed(version, files):
    """
    Checks if anything in ``files`` has changed between version and local HEAD.
    """
    if not version:
        return True
    if not isinstance(files, basestring):
        files = ' '.join(files)
    return "diff" in fabric.api.local("git diff {0} HEAD -- {1}".format(version, files), capture=True)


def supervisor_command(action, name):
    """
    Performs a command on a supervisor process.
    """
    fabric.api.sudo('supervisorctl {0} {1}'.format(action, name))
