from contextlib import contextmanager as _contextmanager

from fabric.api import prefix, local, sudo


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
