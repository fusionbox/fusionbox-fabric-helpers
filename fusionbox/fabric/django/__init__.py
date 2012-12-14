from termcolor import colored
from contextlib import contextmanager
import os
import subprocess

from fabric.api import run, cd

from fusionbox.fabric import fb_env
from fusionbox.fabric.git import get_git_branch
from fusionbox.fabric.update import get_update_function
from fusionbox.fabric.utils import virtualenv, files_changed


def stage(pip=False, migrate=False, syncdb=False, branch=None, role='dev'):
    """
    Updates the remote site files to your local branch head, collects static
    files, migrates, and installs pip requirements if necessary.
    """
    update_function = get_update_function()
    branch = branch or get_git_branch()

    project_name = fb_env.role(role, 'project_name')
    project_loc = fb_env.role(role, 'project_loc')
    virtualenv_loc = fb_env.role(role, 'virtualenv_loc')
    restart_cmd = fb_env.role(role, 'restart_cmd')

    with cd(project_loc):
        version = update_function(branch)

        update_pip = pip or files_changed(version, 'requirements.txt')
        migrate = migrate or files_changed(version, '*/migrations/* {project_name}/settings.py requirements.txt'.format(project_name=project_name))
        syncdb = syncdb or files_changed(version, '*/settings.py')

        with virtualenv(virtualenv_loc):
            if update_pip:
                run('pip install -r ./requirements.txt')

            if syncdb:
                run('python manage.py syncdb')

            if migrate:
                run('python manage.py backupdb')
                run('python manage.py migrate')

            run('python manage.py collectstatic --noinput')

        run(restart_cmd)


def deploy():
    """
    Same as stage, but always uses the live branch and live config settings,
    migrates, and pip installs.
    """
    stage(pip=True, migrate=True, syncdb=True, branch='live', role='live')


def shell():
    """
    Fires up a shell on the live server.
    """
    with cd(fb_env.live_project_loc):
        with virtualenv(fb_env.live_virtualenv_loc):
            run('bash -')


@contextmanager
def run_subprocesses(cmds):
    """
    Returns a list of tuples of command, Popen object.  During __close__, the list
    of processes is polled for unfinished processes and attempts to close them.
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
