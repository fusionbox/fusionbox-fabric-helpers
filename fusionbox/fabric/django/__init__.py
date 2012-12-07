from fabric.api import run, env, cd

from fusionbox.fabric.git_helpers import update_git_with_rsync
from fusionbox.fabric import virtualenv, files_changed


def stage(pip=False, migrate=False, syncdb=False, branch=None):
    """
    stage will update the remote git version to your local HEAD, collectstatic, migrate and
    update pip if necessary.

    Set ``env.project_name`` and ``env.short_name`` appropriately to use.
    ``env.tld`` defaults to ``.com``
    """
    with cd('/var/www/%s%s' % (env.project_name, env.tld)):
        version = update_git_with_rsync(branch or 'HEAD')
        update_pip = pip or files_changed(version, "requirements.txt")
        migrate = migrate or files_changed(version, "*/migrations/* %s/settings.py requirements.txt" % env.project_name)
        syncdb = syncdb or files_changed(version, "*/settings.py")
        with virtualenv(env.short_name):
            if update_pip:
                run("pip install -r ./requirements.txt")
            if syncdb:
                run("python manage.py syncdb")
            if migrate:
                run("python manage.py backupdb")
                run("python manage.py migrate")
            run("python manage.py collectstatic --noinput")
        run("sudo touch /etc/vassals/%s.ini" % env.short_name)


def deploy():
    """
    Like stage, but always migrates, pips, and uses the live branch
    """
    stage(True, True, True, "live")
