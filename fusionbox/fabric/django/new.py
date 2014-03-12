import os
import re
import contextlib
import tempfile
import shutil
from datetime import datetime

from fabric.api import task, run, execute, env, local, sudo
from fabric.context_managers import cd, prefix
from fabric.decorators import roles
from fabric.contrib.project import rsync_project
from fabric.sftp import SFTP
from fabric.colors import red

__all__ = ['stage', 'deploy', 'fetch_dbdump', 'cleanup', 'reload_last_push',
           'rollback']


PROJECTS_PATH = '/var/www/'
DEFAULT_HISTORY_SIZE = 3
DEPLOYMENT_LOCK = 'deployment.lock'
SRC_DIR = 'src'


@contextlib.contextmanager
def cd_project(directory=None):
    path = os.path.join(PROJECTS_PATH, env.project_name)
    if directory is not None:
        path = os.path.join(path, directory)
    with cd(path):
        yield path


@contextlib.contextmanager
def use_tmp_dir():
    directory = tempfile.mkdtemp()
    try:
        yield directory
    finally:
        shutil.rmtree(directory)

@contextlib.contextmanager
def use_virtualenv():
    activate_script = os.path.join(PROJECTS_PATH, env.project_name,
        'virtualenv', 'bin', 'activate')
    with prefix('source {}'.format(activate_script)):
        yield


@contextlib.contextmanager
def atomic_src_update():
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    directory = '{src}.{timestamp}'.format(
        src=SRC_DIR, timestamp=timestamp)

    run('ln -ns {directory} {lock}'.format(
        directory=directory,
        lock=DEPLOYMENT_LOCK
        ))

    try:
        yield directory
    except:
        run('unlink {lock}'.format(lock=DEPLOYMENT_LOCK))
        raise
    else:
        run('mv -f -T {lock} {src}'.format(lock=DEPLOYMENT_LOCK, src=SRC_DIR))



def get_latest_src_dir(position=1):
    with cd_project() as path:
        sftp = SFTP(env.host_string)
        # Honor cd()
        if not os.path.isabs(path):
            path = env.cwd.rstrip('/') + '/' + path.lstrip('/')
        glob_pattern = os.path.join(path, '{}.*'.format(SRC_DIR))
        src_directories = sorted(sftp.glob(glob_pattern))
    return src_directories[-position]


def get_git_ref(name):
    return local('git show-ref {}'.format(name), capture=True).split()[0]


def get_django_version():
    django_version_str = run('django-admin.py version')
    # Parse django version
    m = re.match(r'^([0-9]+)\.([0-9]+).*', django_version_str)
    if m is None:
        raise RuntimeError("Couldn't parse django version {}".format(
           django_version_str))
    return tuple(int(g) for g in m.groups())


def upload_source(gitref, directory):
    """
    Push the new code into a new directory
    """

    with use_tmp_dir() as local_dir:
        local('git archive {ref} | tar x -C {dir}'.format(ref=gitref, dir=local_dir))

        # Add trailing slash for rsync
        if not local_dir.endswith('/'):
            local_dir += '/'

        previous = get_latest_src_dir()

        rsync_project(
            local_dir=local_dir,
            remote_dir=os.path.join(env.cwd, directory),
            delete=True,
            extra_opts='--link-dest={}'.format(previous),
        )

    run('cp -l environment {new}/.env'.format(new=directory))
    run('chmod go+rx {}'.format(directory))


def pip_install(directory):
    """
    Install requirements in this directory
    """
    with use_virtualenv():
        with cd_project(directory):
            run('pip install -r requirements.txt')


def migrate(directory):
    """
    Migrate the database in this directory:
        * If this is using Django < 1.7:
            * python manage.py syncdb --migrate
        * If this is using Django >= 1.7:
            * python manage.py migrate
    """
    with use_virtualenv():
        with cd_project(directory):
            run('python manage.py backupdb')

            if get_django_version() < (1, 7):
                run('python manage.py syncdb --migrate --noinput')
            else:
                run('python manage.py migrate --noinput')


def collectstatic(directory):
    with use_virtualenv():
        with cd_project(directory):
            run('python manage.py collectstatic --noinput')


def reload_uwsgi(directory):
    """
    Update the project's code symlink to the specified directory
    And then touches the vassal
    """
    sudo('touch /etc/vassals/{name}.ini'.format(name=env.vassal_name))


def cleanup_history(size):
    with cd_project():
        # just "rm -rf" does nothing
        run('ls -d -1 {src}.* | head -n -{size:d} | xargs rm -rf'.format(src=SRC_DIR, size=size+1))


def push(gitref, qad):
    """
    Push the last changes

    qad (stands for Quick And Dirty) try to do the minimum work as possible.
      * Doesn't pip install if the requirements.txt didn't change
      * Doesn't migrate if the migrations file didn't change
    """
    with cd_project():
        with atomic_src_update() as directory:
            upload_source(gitref, directory)

            if qad:  # TODO: Try to guess if we need to pip install
                should_pip_install = False
            else:
                should_pip_install = True

            if qad:  # TODO: Try to guess if we need to migrate
                should_migrate = False
            else:
                should_migrate = True


            if should_pip_install:
                pip_install(directory)
            if should_migrate:
                migrate(directory)

            collectstatic(directory)
        reload_uwsgi(directory)
        cleanup_history(DEFAULT_HISTORY_SIZE)


@task
def reload_last_push():
    """
    Reload the code (pip install, migrate, and touch the vassal).
    This should be idem-potent.
    """
    directory = get_latest_src_dir()
    pip_install(directory)
    migrate(directory)
    collectstatic(directory)
    reload_uwsgi(directory)


@task
def rollback():
    """
    Rollback the code to the previous deployed version.
    """
    # TODO:
    #   * cp -rl previous_dir new_dir.timestamp
    #   * find the ghost migration (how?)
    #   * run the migrations back
    print red("** This is not implemented yet **", bold=True)
    local('false')


@task
def cleanup(size=1):
    """
    Cleanup the previous deployed version. Just keep the current deployed one.

    You have to specify the role with -R <live,dev>
    """
    size = int(size)
    if size < 1:
        raise ValueError("We need at list one version")
    return cleanup_history(size)


@task
@roles('live')
def deploy(branch='origin/live'):
    """
    Deploy the live branch to the live server
    """
    local('git fetch --all')
    gitref = get_git_ref(branch)
    return push(gitref, quad=False)


@task
@roles('dev')
def stage(branch='HEAD', qad=True):
    """
    Deploy the current branch to the dev server
    """
    gitref = get_git_ref(branch)
    return push(gitref, qad)


@task
def fetch_dbdump():
    """
    Fetch a database dump (you have to specify the role with -R <live,dev>)
    """
    print red("** This is not implemented yet **", bold=True)
    local('false')
