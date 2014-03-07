import shutil
import tempfile
from StringIO import StringIO

from fabric.api import abort, env, local, put, run, settings
from fabric.contrib.console import confirm
from fabric.contrib.project import rsync_project

from fusionbox.fabric import fb_env
from fusionbox.fabric.git import is_repo_clean, has_git_branch


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

    run("git fetch")

    # Update and get previous remote HEAD
    run("git checkout '{0}'".format(branch))
    remote_head = run("git rev-list --no-merges --max-count=1 HEAD")
    run("git reset --hard origin/{0}".format(branch))

    return remote_head


def update_with_rsync(branch):
    """
    Updates remote site files to local state of ``branch`` using rsync.

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
    files based on the ``fb_env.transport_method`` config setting.
    """
    try:
        return globals()['update_with_{0}'.format(fb_env.transport_method)]
    except KeyError:
        raise NameError('Please set fb_env.transport_method to an accepted value.  Accepted values: {0}'.format([
            i[len('update_with_'):]
            for i in globals().keys()
            if i.startswith('update_with_')
        ]))
