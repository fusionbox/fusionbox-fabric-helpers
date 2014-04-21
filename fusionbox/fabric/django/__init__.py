from termcolor import colored
from contextlib import contextmanager
import os
import subprocess

from fabric.api import run, cd, puts, local, get, env, task

from fusionbox.fabric import fb_env
from fusionbox.fabric.git import get_git_branch
from fusionbox.fabric.update import get_update_function
from fusionbox.fabric.utils import virtualenv, files_changed
from fusionbox.fabric.django.new import get_django_version


@task
def stage(pip=False, migrate=False, syncdb=False, branch=None, post_update=None, role='dev'):
    """
    Updates the remote site files to your local branch head, collects static
    files, migrates, and installs pip requirements if necessary.
    """
    update_function = get_update_function()
    branch = branch or get_git_branch()

    project_name = fb_env.role(role, 'project_name')
    project_path = fb_env.role(role, 'project_path')
    virtualenv_path = fb_env.role(role, 'virtualenv_path')
    restart_cmd = fb_env.role(role, 'restart_cmd')

    with cd(project_path):
        previous_head = update_function(branch)
        puts('Previous remote HEAD: {0}'.format(previous_head))

        if post_update:
            puts('Running post-update hook...')
            post_update()

        update_pip = pip or files_changed(previous_head, 'requirements.txt')
        migrate = migrate or files_changed(previous_head, '*/migrations/* {project_name}/settings.py requirements.txt'.format(project_name=project_name))
        syncdb = syncdb or files_changed(previous_head, '*/settings.py')

        with virtualenv(virtualenv_path):
            if update_pip:
                run('pip install -r ./requirements.txt')

            if syncdb or migrate:
                run('python manage.py backupdb')

            if get_django_version() < (1, 7):  # Django 1.7 introduced migrations
                if syncdb:
                    run('python manage.py syncdb')

                if migrate:
                    run('python manage.py migrate')
            else:
                if syncdb or migrate:
                    run('python manage.py migrate')

            run('python manage.py collectstatic --noinput')

        run(restart_cmd)


@task
def deploy(post_update=None):
    """
    Same as stage, but always uses the live branch and live config settings,
    migrates, and pip installs.
    """
    stage(pip=True, migrate=True, syncdb=True, branch='live', post_update=post_update, role='live')


def shell():
    """
    Fires up a shell on the live server.
    """
    with cd(fb_env.live_project_path):
        with virtualenv(fb_env.live_virtualenv_path):
            run('bash -')


def sync_db(role):
    """
    Downloads the latest remote (live or dev) database backup and loads it on your local
    machine.
    """
    remote_project_path = fb_env.role(role, 'project_path')
    remote_virtualenv_path = fb_env.role(role, 'virtualenv_path')
    remote_backups_dir = fb_env.role(role, 'backups_dir')

    local('python manage.py backupdb')

    with cd(remote_project_path):
        with virtualenv(remote_virtualenv_path):
            run('python manage.py backupdb --backup-name=sync --pg-dump-options="--no-owner --no-privileges"')

            # Download
            get(
                '{remote_backups_dir}/*-sync.*.gz'.format(
                    remote_backups_dir=remote_backups_dir,
                ),
                './{local_backups_dir}/'.format(
                    local_backups_dir=fb_env.local_backups_dir,
                ),
            )

    local('python manage.py restoredb --backup-name=sync')


sync_with_live_db = lambda: sync_db('live')
sync_with_dev_db = lambda: sync_db('dev')


def sync_media(role):
    """
    Synchronizes the latest remote (live or dev) media directory with your
    local media directory.
    """
    remote = env.roledefs[role][0]
    remote_media_path = fb_env.role(role, 'media_path') + '/'

    # Rsync has weird syntax for the target directory
    local_media_dir = './' + fb_env.local_media_dir

    local('rsync -avz --progress {remote}:{remote_media_path} {local_media_dir}'.format(
        remote=remote,
        remote_media_path=remote_media_path,
        local_media_dir=local_media_dir,
    ))


sync_with_live_media = lambda: sync_media('live')
sync_with_dev_media = lambda: sync_media('dev')


@contextmanager
def run_subprocesses(cmds):
    """
    Returns a list of tuples of command, Popen object.  During __close__, the
    list of processes is polled for unfinished processes and attempts to close
    them.
    """
    processes = []
    cwd = os.getcwd()
    try:
        for dir, cmd in cmds:
            p = subprocess.Popen(cmd, shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 cwd=os.path.join(cwd, dir))
            processes.append((cmd, p))
        yield processes
    finally:
        # We clean up any subprocesses that haven't finished with a SIGTERM
        procs_to_term = filter(lambda p: p[1].poll() is None, processes)
        try:
            [p.terminate() for _, p in procs_to_term]
            [p.wait() for _, p in procs_to_term]
        except KeyboardInterrupt:
            # User issued an interrupt, send SIGKILL to end immediately
            [p.kill() for _, p in procs_to_term if p.poll() is None]
            [p.wait() for _, p in procs_to_term]


def runserver():
    """
    Runs the local django server, starting up celery workers and/or the solr
    server if needed.

    The following fb_env variables must be present in your fabfile for their
    related processes to be started.  Each should be a 2-tuple of directory and
    command to run.

    - ``runserver_cmd``: ``('.', './manage.py runserver')``
    - ``celery_cmd``: ``('.', './manage.py celery worker -c 2 --autoreload')``
    - ``solr_cmd``: ``('solr', 'java -jar start.jar')``
    """
    commands = filter(bool, (
        getattr(fb_env, 'runserver_cmd', None),
        getattr(fb_env, 'celery_cmd', None),
        getattr(fb_env, 'solr_cmd', None),
    ))
    if not commands:
        print "No commands found.  Please check that you have set the necessary environment variables"

    def read_message(fd):
        ret = ''
        while True:
            out = fd.read(1)
            ret += out
            if out == '':
                break
        return ret

    message_prefix = colored('[{command}]', 'blue', attrs=['bold'])
    error_prefix = colored('[{command}]', 'white', 'on_red', attrs=['bold'])
    output = u'{prefix} {message}'

    with run_subprocesses(commands) as processes:
        for cmd, p in processes:
            while p.poll() is None:
                message = read_message(p.stdout)
                error = read_message(p.stderr)
                if message:
                    print (output.format(
                        prefix=message_prefix.format(command=cmd),
                        message=message))
                if error:
                    print (output.format(
                        prefix=error_prefix.format(command=cmd),
                        message=error))


def obfuscate():
    """
    Compile all source files to byte code, then remove them.
    """
    run('python -m compileall .')
    run("find -type f -name '*.py' -not -name 'settings_local.py' -not -name 'manage.py' -delete")


def obfuscate_decorator(role):
    """
    Given a fabric action, this will run obfuscate() after it with config
    settings for the specified role.
    """
    def decorator(old_fn):
        def new_fn(*args, **kwargs):
            retval = old_fn(*args, **kwargs)

            project_path = fb_env.role(role, 'project_path')
            virtualenv_path = fb_env.role(role, 'virtualenv_path')

            with cd(project_path):
                # Use the venv so we have the right python version
                with virtualenv(virtualenv_path):
                    obfuscate()

            return retval
        return new_fn
    return decorator
