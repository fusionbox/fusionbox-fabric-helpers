from fabric.api import run, local, puts, cd, roles, env

from fusionbox.fabric.git_helpers import get_git_branch, update_git_with_rsync, update_git_with_pull


def get_fborm_folder():
    """
    Return the fborm directory.
    """
    branch = get_git_branch()
    return '/var/www/fborm%s/' % ("" if branch == "master" else ":" + branch)


@roles('dev')
def correct():
    """
    Correct permissions on the dev server.
    """
    run("sudo chgrp -R fusionbox /var/www/%s" % env.project_name)
    run("sudo chmod -R g+rwx /var/www/%s" % env.project_name)
    run("sudo chmod o+w /var/www/%s/archive" % env.project_name)
    run("sudo chmod o+w /var/www/%s/public_html/content" % env.project_name)
    run("sudo chmod o+w /var/www/%s/public_html/img" % env.project_name)
    run("sudo chmod -R g+rwx %s" % get_fborm_folder())
    run("sudo chmod o+w %s" % get_fborm_folder())
    run("rm -f /var/www/%s/.git/deploy_bundle" % env.project_name)


@roles('dev')
def stage():
    """
    Stage will update the dev server with any changes.
    """
    local('git pull origin %s' % get_git_branch())
    local('git push origin %s' % get_git_branch())
    with cd('/var/www/%s/' % env.project_name):
        update_git_with_rsync(get_git_branch())
        run("./fbmvc migrate latest")


@roles('live')
def deploy():
    """
    Deploy changes to the live server
    """
    with cd('/var/www/%s/' % env.project_name):
        previous_head = update_git_with_pull('live')
        puts("Previous live HEAD: %s" % previous_head)
        update_git_with_pull('live')
        run("./fbmvc migrate latest")


@roles('live')
def rollback(rev):
    """
    Rollback the live server to a specified commit.
    """
    with cd('/var/www/%s/' % env.project_name):
        run("git checkout '%s'" % rev)
