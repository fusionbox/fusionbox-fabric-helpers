import os
import re
import contextlib
import tempfile
import shutil
import getpass
import sys
from datetime import timedelta
from StringIO import StringIO
from collections import namedtuple

from fabric.api import task, run, env, local, sudo, settings, get
from fabric.context_managers import cd, prefix, hide
from fabric.decorators import roles
from fabric.contrib.project import rsync_project
from fabric.contrib.files import append, exists
from fabric.contrib.console import confirm
from fabric.sftp import SFTP
from fabric.colors import red, blue
from fabric.utils import abort

__all__ = ['stage', 'deploy', 'fetch_dbdump', 'cleanup', 'reload_last_push',
           'rollback', 'django']


PROJECTS_PATH = '/var/www/'
DEFAULT_HISTORY_SIZE = 3
DEPLOYMENT_LOCK = 'deployment.lock'
DEPLOY_LOG = 'deploy.log'
SRC_DIR = 'src'
REQUIREMENT_FILE = 'requirements.txt'
SRC_DIRNAMES_RE = re.compile(r'^%s\.(\d{5})$' % re.escape(SRC_DIR))
VIRTUALENV = 'virtualenv'


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
        src=SRC_DIR, number=max(numbers_list + [0]) + 1)

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
    dirname_list = (os.path.basename(d) for d in get_src_dir_list())
    return [int(SRC_DIRNAMES_RE.match(d).group(1))
            for d in dirname_list if SRC_DIRNAMES_RE.match(d) is not None]


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


def generate_pyc():
    # compilation can fail
    with settings(warn_only=True):
        run('python -m compileall . > /dev/null')


def upload_source(gitref, directory):
    """
    Push the new code into a new directory
    """

    with use_tmp_dir() as local_dir:
        local('git archive {ref} | tar x -C {dir}'.format(ref=gitref, dir=local_dir))

        # Add trailing slash for rsync
        if not local_dir.endswith('/'):
            local_dir += '/'

        rsync_project(
            local_dir=local_dir,
            remote_dir=os.path.join(env.cwd, directory),
            delete=True,
            extra_opts=' '.join('--link-dest={}'.format(d) for d in get_src_dir_list()),
            # Fabric defaults to -pthrvz
            # -t preserve the modification time. We want to ignore that.
            # -v print the file being updated
            # We replaced these by:
            # -c will use checksum to compare files
            # -i will print what kind of transfer has been done (copy/upload/...)
            default_opts='-pchriz',
        )

    run('cp -l environment {new}/.env'.format(new=directory))
    run('chmod go+rx {}'.format(directory))


def pip_install():
    """
    Install requirements in this directory
    """
    run('pip install --upgrade -r requirements.txt')


def migrate(backupdb):
    """
    Migrate the database in this directory:
        * If this is using Django < 1.7:
            * python manage.py syncdb --migrate
        * If this is using Django >= 1.7:
            * python manage.py migrate
    """
    if backupdb:
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
    possibilities_templates = [
        '/etc/vassals/{name}.ini',
        '/etc/uwsgi-emperor/vassals/{name}.ini',
    ]
    possibilities = [f.format(name=env.vassal_name) for f in possibilities_templates]

    for fname in possibilities:
        if exists(fname):
            sudo('touch {}'.format(fname))
            break
    else:
        raise RuntimeError("Couldn't find the vassal file in %s" % possibilities)


def cleanup_history(size, superclean=False):
    if size < 0:
        raise ValueError("The history size can't be negative")
    with cd_project():
        current_src = os.path.basename(run('readlink -f {}'.format(SRC_DIR)))

        assert SRC_DIRNAMES_RE.match(current_src) is not None, "This server has weird src directory names"
        current_number = int(SRC_DIRNAMES_RE.match(current_src).group(1))

        src_directories = [os.path.basename(d) for d in get_src_dir_list()]
        # src directory that have been deployed
        deployed_src = [dirname for dirname in src_directories
                        if int(SRC_DIRNAMES_RE.match(dirname).group(1)) < current_number]
        deployed_src.sort(reverse=True)

        to_remove = deployed_src[size:]

        if superclean:
            dirty_src = [dirname for dirname in src_directories
                         if int(SRC_DIRNAMES_RE.match(dirname).group(1)) > current_number]
            to_remove += dirty_src

        if to_remove:
            run('rm -rf {}'.format(' '.join(to_remove)))


def is_there_a_diff(file1, file2):
    with settings(hide('stdout', 'warnings'), warn_only=True):
        return run('diff {a} {b}'.format(a=file1, b=file2)).failed


def count_migrations(directory):
    with hide('stdout'):
        migrations_list = run('find . -path "{}/*/migrations/*.py" -print0'.format(directory))
    return len(migrations_list.split('\0'))


def is_ancestor_of(old, new):
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        ret = local('git merge-base --is-ancestor {old} {new}'.format(
            old=old, new=new,
        ), capture=True)

        if ret.return_code not in (0, 1, 128):
            # 0 -- is ancestor
            # 1 -- not ancestor
            # 128 -- invalid ref (probably not in the local repo) (same as not ancestor)
            # anything else -- report the error
            sys.stderr.write(ret.stderr)
            abort(red(
                "Couldn't check ancestry, are you running an old version of git?",
                bold=True,
            ))

        return ret.succeeded


LogEntry = namedtuple('LogEntry', ['human_date', 'username', 'dir', 'hash'])

def get_deploy_log():
    with settings(hide('running', 'stdout', 'stderr', 'warnings'), warn_only=True):
        log = StringIO()
        get(DEPLOY_LOG, log)
        return [LogEntry(*i.split('\t')) for i in log.getvalue().split('\n') if len(i)]


def push(gitref, qad, backupdb):
    """
    Push the last changes

    qad (stands for Quick And Dirty) try to do the minimum work as possible.
      * Doesn't pip install if the requirements.txt didn't change
      * Doesn't migrate if the migrations file didn't change
    """
    with cd_project():
        with atomic_src_update() as directory:
            try:
                previous_deploy = get_deploy_log()[-1]
            except IndexError:
                # first deploy
                pass
            else:
                if not is_ancestor_of(previous_deploy.hash, gitref):
                    message = blue(
                        "Warning: Going to update from {old} (deployed by {user}) to {new},"
                        " which is not a fast-forward. Continue?".format(
                            old=previous_deploy.hash[:8],
                            new=gitref[:8],
                            user=previous_deploy.username,
                        ),
                        bold=True,
                    )
                    if not confirm(message, default=False):
                        abort("Aborted.")

            upload_source(gitref, directory)

            try:
                previous_source = os.path.basename(
                    run('readlink -f {}'.format(SRC_DIR)))
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
                    migrate(backupdb)

                collectstatic()

            with cd(directory):
                generate_pyc()

            if should_pip_install:
                # "pip install" generates pyc files in site-packages
                # but "pip install -e" doesn't generate any pyc files
                virtualenv_src = os.path.join(VIRTUALENV, 'src')
                with cd(virtualenv_src):
                    generate_pyc()

            with hide('running', 'stdout'):
                server_time = run('TZ=America/Denver date')
            append(DEPLOY_LOG, '{date}:\t{user}\t{dir}\t{ref}'.format(
                date=server_time, ref=gitref, dir=directory, user=getpass.getuser(),
            ))

        reload_uwsgi()
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
def cleanup(size=1, superclean=True):
    """
    Cleanup the previous deployed version. Just keep the current deployed one.

    You have to specify the role with -R <live,dev>
    """
    size = int(size)
    if size < 1:
        raise ValueError("The history size can't be less than 1")
    return cleanup_history(size-1, superclean=is_true(superclean))


@task
@roles('live')
def deploy(branch='origin/live', force=False, backupdb=True):
    """
    Deploy the live branch to the live server
    """
    env.force = is_true(force)
    local('git fetch --all')
    gitref = get_git_ref(branch)
    return push(gitref, qad=False, backupdb=is_true(backupdb))


@task
@roles('dev')
def stage(branch='HEAD', qad=True, force=False, backupdb=True):
    """
    Deploy the current branch to the dev server
    """
    env.force = is_true(force)
    gitref = get_git_ref(branch)
    return push(gitref, is_true(qad), is_true(backupdb))


@task
def fetch_dbdump():
    """
    Fetch a database dump (you have to specify the role with -R <live,dev>)
    """
    print red("** This is not implemented yet **", bold=True)
    local('false')


@task
def django(command):
    """
    Run a shell on the server
    """
    src_directory = get_latest_src_dir()
    with cd_project(src_directory):
        with use_virtualenv():
            run("python manage.py {}".format(command))
