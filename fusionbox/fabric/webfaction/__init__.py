from fabric.api import run, env, cd, puts

from fusionbox.fabric import virtualenv
from fusionbox.fabric.git_helpers import get_update_function
from fusionbox.fabric.django import stage


stage = stage


def deploy():
    update_function = get_update_function()
    with cd(env.live_project_dir):
        previous_head = update_function("live")
        puts("Previous live HEAD: {0}".format(previous_head))

        with virtualenv(env.live_virtual_env):
            run("pip install -r ./requirements.txt")
            run("./manage.py backupdb")
            run("./manage.py migrate")
            run("./manage.py collectstatic --noinput")

        run(env.live_restart_cmd)


def rollback(rev):
    """
    Checks out the specified commit or branch on the live server.
    """
    with cd(env.live_project_dir):
        run("git checkout '{0}'".format(rev))


def shell():
    """
    Fires up a shell on the live server.
    """
    with cd(env.live_project_dir):
        with virtualenv(env.live_virtual_env):
            run("bash -")
