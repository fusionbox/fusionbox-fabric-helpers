import os
import re
import contextlib
import tempfile
import shutil
import getpass
from datetime import timedelta

from fabric.api import task, run, env, local, sudo, settings
from fabric.context_managers import cd, prefix, hide
from fabric.decorators import roles
from fabric.contrib.project import rsync_project
from fabric.contrib.files import append
from fabric.sftp import SFTP
from fabric.colors import red
from fabric.utils import abort

__all__ = ['stage', 'deploy', 'fetch_dbdump', 'cleanup', 'reload_last_push',
           'rollback']


PROJECTS_PATH = '/var/www/'
DEFAULT_HISTORY_SIZE = 3
DEPLOYMENT_LOCK = 'deployment.lock'
DEPLOY_LOG = 'deploy.log'
SRC_DIR = 'src'
REQUIREMENT_FILE = 'requirements.txt'


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
    numbers_list = get_src_dir_numbers()
    directory = '{src}.{number:05d}'.format(
        src=SRC_DIR, number=max(numbers_list) + 1)

    if env.force:
        run('rm -f {lock}'.format(lock=DEPLOYMENT_LOCK))

    with settings(warn_only=True):
        result = run('ln -ns {directory} {lock}'.format(
            directory=directory,
            lock=DEPLOYMENT_LOCK
            ))

    if result.failed:
        with hide('running', 'stdout', 'stderr'):
            current_time = int(run('date +%s'))
            locked_at = int(run('stat -c "%Y" {lock}'.format(lock=DEPLOYMENT_LOCK)))
            locked_for = timedelta(seconds=current_time-locked_at)
            abort(red(
                "Someone else is holding the deployment lock (For {locked_for})."
                " Rerun with force=1 to kick them off (could be dangerous).".format(
                    locked_for=locked_for
                ),
                bold=True
            ))

    try:
        yield directory
    except:
        run('unlink {lock}'.format(lock=DEPLOYMENT_LOCK))
        raise
    else:
        run('mv -f -T {lock} {src}'.format(lock=DEPLOYMENT_LOCK, src=SRC_DIR))


def is_true(b):
    """
    Checks if an argument passed through the command line is true
    """
    return str(b).lower() not in ('no', 'n', 'false', 'f', 'a', 'abort', '0')


def get_src_dir_list():
    with cd_project() as path:
        sftp = SFTP(env.host_string)
        # Honor cd()
        path = os.path.join(env.cwd, path)
        glob_pattern = os.path.join(path, '{}.*'.format(SRC_DIR))
        return sftp.glob(glob_pattern)


def get_latest_src_dir(position=1):
    src_directories = sorted(get_src_dir_list())
    return src_directories[-position]


def get_src_dir_numbers():
    dirname_re = re.compile(r'^%s\.(\d{5})$' % re.escape(SRC_DIR))
    dirname_list = (os.path.basename(d) for d in get_src_dir_list())
    return [int(dirname_re.match(d).group(1))
            for d in dirname_list if dirname_re.match(d) is not None]


def get_git_ref(name):
    return local('git rev-parse {}'.format(name), capture=True)


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
            # Fabric defaults to -pthrvz
            # -t preserve the modification time. We want to ignore that.
            # -c will use checksum to compare files
            default_opts='-pchrvz',
        )

    run('cp -l environment {new}/.env'.format(new=directory))
    run('chmod go+rx {}'.format(directory))


def pip_install():
    """
    Install requirements in this directory
    """
    run('pip install -r requirements.txt')


def migrate():
    """
    Migrate the database in this directory:
        * If this is using Django < 1.7:
            * python manage.py syncdb --migrate
        * If this is using Django >= 1.7:
            * python manage.py migrate
    """
    run('python manage.py backupdb')

    if get_django_version() < (1, 7):
        run('python manage.py syncdb --migrate --noinput')
    else:
        run('python manage.py migrate --noinput')


def collectstatic():
    run('python manage.py collectstatic --noinput')


def reload_uwsgi():
    """
    Update the project's code symlink to the specified directory
    And then touches the vassal
    """
    sudo('touch /etc/vassals/{name}.ini'.format(name=env.vassal_name))


def cleanup_history(size):
    with cd_project():
        # just "rm -rf" does nothing
        run('ls -d -1 {src}.* | head -n -{size:d} | xargs rm -rf'.format(src=SRC_DIR, size=size+1))


def is_there_a_diff(file1, file2):
    with settings(hide('stdout', 'warnings'), warn_only=True):
        return run('diff {a} {b}'.format(a=file1, b=file2)).failed


def count_migrations(directory):
    with hide('stdout'):
        migrations_list = run('find {} -path "*/migrations/*.py" -print0'.format(directory))
    return len(migrations_list.split('\0'))


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

            try:
                previous_source = get_latest_src_dir(2)
            except IndexError:
                should_pip_install = True
                should_migrate = True
            else:
                if qad:
                    # Try to guess if we should pip install
                    should_pip_install = is_there_a_diff(
                        os.path.join(directory, REQUIREMENT_FILE),
                        os.path.join(previous_source, REQUIREMENT_FILE),
                    )
                else:
                    should_pip_install = True

                if qad:
                    # Try to guess if there are extra migrations
                    migrations_now = count_migrations(directory)
                    migrations_before = count_migrations(previous_source)
                    # If we should pip install, new pip packages might
                    # introduce migrations.
                    should_migrate = should_pip_install or migrations_now != migrations_before
                else:
                    should_migrate = True

            with contextlib.nested(use_virtualenv(), cd(directory)):
                if should_pip_install:
                    pip_install()
                if should_migrate:
                    migrate()

                collectstatic()

        reload_uwsgi()

        with hide('running', 'stdout'):
            server_time = run('TZ=America/Denver date')
        append(DEPLOY_LOG, '{date}:\t{user}\t{dir}\t{ref}'.format(
            date=server_time, ref=gitref, dir=directory, user=getpass.getuser(),
        ))

        cleanup_history(DEFAULT_HISTORY_SIZE)


@task
def reload_last_push():
    """
    Reload the code (pip install, migrate, and touch the vassal).
    This should be idem-potent.
    """
    directory = get_latest_src_dir()
    with contextlib.nested(cd_project(directory), use_virtualenv()):
        pip_install()
        migrate()
        collectstatic()
        reload_uwsgi()


@task
def rollback():
    """
    Rollback the code to the previous deployed version.
    """
    # TODO:
    #   * cp -rl previous_dir new_dir.last_number
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
def deploy(branch='origin/live', force=False):
    """
    Deploy the live branch to the live server
    """
    env.force = is_true(force)
    local('git fetch --all')
    gitref = get_git_ref(branch)
    return push(gitref, qad=False)


@task
@roles('dev')
def stage(branch='HEAD', qad=True, force=False):
    """
    Deploy the current branch to the dev server
    """
    env.force = is_true(force)
    gitref = get_git_ref(branch)
    return push(gitref, is_true(qad))


@task
def fetch_dbdump():
    """
    Fetch a database dump (you have to specify the role with -R <live,dev>)
    """
    print red("** This is not implemented yet **", bold=True)
    local('false')
