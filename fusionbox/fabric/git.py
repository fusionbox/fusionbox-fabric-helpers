from fabric.api import local, run, settings


def get_git_branch():
    """
    Returns the name of the active local git branch.
    """
    if local("echo $TRAVIS", capture=True):
        return local("echo $TRAVIS_BRANCH", capture=True)
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
