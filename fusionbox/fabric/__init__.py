import shutil
import tempfile
from contextlib import contextmanager as _contextmanager
from StringIO import StringIO

from fabric.api import (
    abort, cd, env, local,
    prefix, put, run, settings,
    sudo,
)
from fabric.contrib.console import confirm
from fabric.contrib.project import rsync_project


# Default fabric config
env.forward_agent = True
env.roledefs = {
    'dev': ['dev.fusionbox.com'],
}

# Default fusionbox helper config
env.transport_method = 'git'
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


##|
##| General helpers
##|
@_contextmanager
def virtualenv(dir):
    """
    Context manager to run all commands under the python virtual env at ``dir``.
    """
    with prefix('source {workon_home}/{dir}/bin/activate'.format(dir=dir, **env)):
        yield


@_contextmanager
def project_directory():
    """
    Context manager to run all commands within the project root directory.
    Uses ``env.project_name`` and ``env.tld``.
    """
    with cd('/var/www/{project_name}{tld}'.format(**env)):
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


##|
##| Git helpers
##|
def get_git_branch():
    """
    Returns the name of the active local git branch.
    """
    return local("git branch --no-color 2> /dev/null|grep '^*' | sed 's/^* //'", capture=True)


def has_git_branch(branch):
    """
    Checks if ``branch`` is available in the remote git repository.
    """
    with settings(warn_only=True):
        return run("git branch --no-color 2> /dev/null|grep '^*\? \+{0}$'".format(branch)).succeeded


def is_local_repo_clean():
    """
    Checks if there are uncommitted changes in the local git repository.
    """
    with settings(warn_only=True):
        return local("git status 2>&1|grep 'nothing to commit' > /dev/null").succeeded


def is_repo_clean():
    """
    Checks if there are uncommitted changes in the remote git repository.
    """
    with settings(warn_only=True):
        return run("git status 2>&1|grep 'nothing to commit' > /dev/null").succeeded


##|
##| Update methods
##|
def update_with_git(branch):
    """
    Updates the remote git repository to ``branch`` using git pull.

    Returns the commit hash of the remote HEAD before it was updated.
    """
    # Stash if repo not clean
    if not is_repo_clean():
        run("git status")
        if not confirm("Remote repo is not clean, stash and continue?"):
            abort("Remote repo dirty, aborting...")
        run("git stash")

    # If branch is not on server, get it
    if not has_git_branch(branch):
        run("git fetch origin {0}".format(branch))
        run("git fetch")

    # Update and get previous remote HEAD
    run("git checkout '{0}'".format(branch))
    remote_head = run("git rev-list --no-merges --max-count=1 HEAD")
    run("git pull origin {0}".format(branch))

    return remote_head


def update_with_rsync(branch):
    """
    Updates remote site directory to local state of ``branch`` using rsync.

    Returns the commit hash of remote version before update.
    """
    with settings(warn_only=True):
        remote_head = run("cat static/.git_version.txt")
        if remote_head.failed:
            remote_head = None
    try:
        loc = tempfile.mkdtemp()
        put(StringIO(local('git rev-parse %s' % branch, capture=True) + "\n"), 'static/.git_version.txt', mode=0775)
        local("cd `git rev-parse --show-toplevel` && git archive %s | tar xf - -C %s" % (branch, loc))
        local("chmod -R g+rwX %s" % (loc))  # force group permissions
        # env.cwd is documented as private, but I'm not sure how else to do this
        with settings(warn_only=True):
            loc = loc + '/'  # without this, the temp directory will get uploaded instead of just its contents
            rsync_project(env.cwd, loc, extra_opts='--chmod=g=rwX,a+rX -l')
    finally:
        shutil.rmtree(loc)
    return remote_head


def get_update_function():
    """
    Returns the update function which will be used to update the remote site
    files.  Uses env.transport_method config value.
    """
    try:
        return globals()['update_with_{0}'.format(env.transport_method)]
    except KeyError:
        raise NameError('Please set env.transport_method to an accepted value.  Accepted values: {0}'.format([
            i[len('update_with_'):]
            for i in globals().keys()
            if i.startswith('update_with_')
        ]))
