from termcolor import colored
from contextlib import contextmanager
import os
import subprocess

from fabric.api import run

from fusionbox.fabric import virtualenv, files_changed, project_directory, get_update_function, get_git_branch, fb_env


@contextmanager
def run_subprocesses(cmds):
    """
    Returns a list of tuples of command, Popen object.  During __close__, the list
    of processes is polled for unfinished processes and attempts to close them.
    """
    processes = []
    cwd = os.getcwd()
    for dir, cmd in cmds:
        p = subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             cwd=os.path.join(cwd, dir))
        processes.append((cmd, p))
    try:
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


def stage(pip=False, migrate=False, syncdb=False, branch=None):
    """
    Updates the remote git version to your local branch head, collects static
    files, migrates, and installs pip requirements if necessary.

    Set ``fb_env.project_name`` and ``fb_env.project_abbr`` appropriately to use.
    ``fb_env.tld`` defaults to ``.com``
    """
    update_function = get_update_function()

    with project_directory():
        version = update_function(branch or get_git_branch())

        update_pip = pip or files_changed(version, "requirements.txt")
        migrate = migrate or files_changed(version, "*/migrations/* {project_name}/settings.py requirements.txt".format(**fb_env))
        syncdb = syncdb or files_changed(version, "*/settings.py")

        with virtualenv(fb_env.project_abbr):
            if update_pip:
                run("pip install -r ./requirements.txt")

            if syncdb:
                run("python manage.py syncdb")

            if migrate:
                run("python manage.py backupdb")
                run("python manage.py migrate")

            run("python manage.py collectstatic --noinput")

        run("sudo touch /etc/vassals/{project_abbr}.ini".format(**fb_env))


def deploy():
    """
    Same as stage, but always uses the live branch, migrates, and pip installs.
    """
    stage(True, True, True, "live")


def shell():
    """
    Fires up a shell on the remote server.
    """
    with project_directory():
        with virtualenv(fb_env.project_abbr):
            run("bash -")


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
