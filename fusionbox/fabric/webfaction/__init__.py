from fabric.api import run, roles, env, cd, puts

from fusionbox.fabric import virtualenv, files_changed
from fusionbox.fabric.git_helpers import get_git_branch, update_git_with_pull


@roles("dev")
def correct():
    run("sudo chgrp -R fusionbox /var/www/{0}".format(env.full_name))
    run("sudo chmod -R g+rwx /var/www/{0}".format(env.full_name))


@roles("dev")
def stage(pip=False, migrate=False):
    with cd("/var/www/{0}/".format(env.full_name)):
        version = update_git_with_pull(get_git_branch())
        update_pip = pip or files_changed(version, "requirements.txt")
        migrate = migrate or files_changed(version, "*/migrations/* {0}/settings.py requirements.txt".format(env.abbr_name))

        with virtualenv("/var/python-environments/{0}".format(env.abbr_name)):
            if update_pip:
                run("pip install -r ./requirements.txt")
            if migrate:
                run("./manage.py backupdb")
                run("./manage.py migrate")
            run("./manage.py collectstatic --noinput")

        run("sudo touch /etc/vassals/{0}.ini".format(env.abbr_name))


@roles("live")
def deploy():
    with cd(env.live_project_dir):
        previous_head = update_git_with_pull("live")
        puts("Previous live HEAD: {0}".format(previous_head))

        with virtualenv(env.live_virtual_env):
            run("pip install -r ./requirements.txt")
            run("./manage.py backupdb")
            run("./manage.py migrate")
            run("./manage.py collectstatic --noinput")

        run(env.live_restart_cmd)


@roles("live")
def rollback(rev):
    """
    Checks out the specified commit or branch on the live server.
    """
    with cd(env.live_project_dir):
        run("git checkout '{0}'".format(rev))


@roles("live")
def shell():
    """
    Fires up a shell on the live server.
    """
    with cd(env.live_project_dir):
        with virtualenv(env.live_virtual_env):
            run("bash -")
