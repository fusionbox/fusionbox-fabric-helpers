from contextlib import contextmanager as _contextmanager

from fabric.api import prefix, env, local


env.workon_home = '/var/python-environments'
env.tld = '.com'


@_contextmanager
def virtualenv(dir):
    """
    Context manager to run all commands under a specified python virtual env.
    """
    with prefix('source %s/%s/bin/activate' % (env.workon_home, dir)):
        yield


def files_changed(version, files):
    """
    Between version and HEAD, has anything in files changed?
    """
    if not version:
        return True
    if not isinstance(files, basestring):
        files = ' '.join(files)
    return "diff" in local("git diff %s HEAD -- %s" % (version, files), capture=True)
