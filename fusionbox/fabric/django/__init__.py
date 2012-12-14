import os
import subprocess

from fabric.api import run, cd

from fusionbox.fabric import virtualenv, files_changed, get_update_function, get_git_branch, fb_env


def stage(
    pip=False, migrate=False, syncdb=False,
    branch=None, role='dev',
):
    """
    Updates the remote git version to your local branch head, collects static
    files, migrates, and installs pip requirements if necessary.

    Set ``fb_env.project_name`` and ``fb_env.project_abbr`` appropriately to use.
    ``fb_env.tld`` defaults to ``.com``
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
    Same as stage, but always uses the live branch, migrates, and pip installs.
    """
    stage(
        pip=True,
        migrate=True,
        syncdb=True,
        branch='live',
        role='live',
    )


def shell():
    """
    Fires up a shell on the remote server.
    """
    with cd(fb_env.live_project_loc):
        with virtualenv(fb_env.live_virtualenv_loc):
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
