import subprocess
import os

from fabric.api import run, env

from fusionbox.fabric.git_helpers import update_git_with_rsync
from fusionbox.fabric import virtualenv, files_changed, project_directory


def stage(pip=False, migrate=False, syncdb=False, branch=None):
    """
    stage will update the remote git version to your local HEAD, collectstatic, migrate and
    update pip if necessary.

    Set ``env.project_name`` and ``env.project_abbr`` appropriately to use.
    ``env.tld`` defaults to ``.com``
    """
    with project_directory():
        version = update_git_with_rsync(branch or 'HEAD')
        update_pip = pip or files_changed(version, "requirements.txt")
        migrate = migrate or files_changed(version, "*/migrations/* {project_name}/settings.py requirements.txt".format(**env))
        syncdb = syncdb or files_changed(version, "*/settings.py")
        with virtualenv(env.project_abbr):
            if update_pip:
                run("pip install -r ./requirements.txt")
            if syncdb:
                run("python manage.py syncdb")
            if migrate:
                run("python manage.py backupdb")
                run("python manage.py migrate")
            run("python manage.py collectstatic --noinput")
        run("sudo touch /etc/vassals/{project_abbr}.ini".format(**env))


def deploy():
    """
    Like stage, but always migrates, pips, and uses the live branch
    """
    stage(True, True, True, "live")


def shell():
    """
    Fires up a shell.
    """
    with project_directory():
        with virtualenv(env.project_abbr):
            run("bash -")


def runserver():
    """
    Runs the local django server, starting up celery workers and/or the solr
    server if needed.

    The following env variables must be present in your fabfile for their
    related processes to be started.  Each should be a 2-tuple of directory and
    command to run.

    `runserver_cmd`: `('.', './manage.py runserver')`
    `celery_cmd`: `('.', './manage.py celery worker -c 2 --autoreload')`
    `solr_cmd`: `('solr', 'java -jar start.jar')`
    """
    commands = filter(bool, (
        getattr(env, 'runserver_cmd', None),
        getattr(env, 'celery_cmd', None),
        getattr(env, 'solr_cmd', None),
    ))
    if not commands:
        print "No commands found.  Please check that you have set the necessary environment variables"
    processes = []
    cwd = os.getcwd()
    for dir, command in commands:
        processes.append(subprocess.Popen(command, shell=True, cwd=os.path.join(cwd, dir)))

    try:
        [p.wait() for p in processes]
    except KeyboardInterrupt:
        try:
            [p.terminate() for p in processes]
            [p.wait() for p in processes]
        except KeyboardInterrupt:
            for p in processes:
                if p.poll() is None:
                    p.kill()
            [p.wait() for p in processes]
