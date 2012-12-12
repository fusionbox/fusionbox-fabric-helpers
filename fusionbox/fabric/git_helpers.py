import tempfile
import shutil
from StringIO import StringIO

from fabric.api import local, run, settings, abort, put, env
from fabric.contrib.console import confirm
from fabric.contrib.project import rsync_project


def get_git_branch():
    """
    Returns the local git branch name
    """
    return local("git branch --no-color 2> /dev/null|grep '^*' | sed 's/^* //'", capture=True)


def has_git_branch(branch):
    """
    Returns whether or not the branch is available.
    """
    with settings(warn_only=True):
        return run("git branch --no-color 2> /dev/null|grep '^*\? \+{0}$'".format(branch)).succeeded


def is_local_repo_clean():
    """
    Check if the local git repository is clean.
    """
    with settings(warn_only=True):
        return local("git status 2>&1|grep 'nothing to commit' > /dev/null").succeeded


def is_repo_clean():
    """
    Chech if the remote git repository is clean.
    """
    with settings(warn_only=True):
        return run("git status 2>&1|grep 'nothing to commit' > /dev/null").succeeded


def update_git_with_pull(branch):
    """
    Updates the remote git repo to ``branch`` using git pull.

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


def update_git_with_rsync(branch):
    """
    Updates the remote git repo to ``branch`` using rsync.

    Returns the commit hash of the remote HEAD before it was updated.
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
