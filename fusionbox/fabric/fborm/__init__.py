from fabric.api import run, local, puts, cd, roles, env

from fusionbox.fabric.git_helpers import get_git_branch, update_with_pull


def get_fborm_folder():
    branch = get_git_branch()
    return '/var/www/fborm%s/' % ("" if branch == "master" else ":" + branch)


@roles('dev')
def correct():
    run("sudo chgrp -R fusionbox /var/www/%s" % env.project_name)
    run("sudo chmod -R g+rwx /var/www/%s" % env.project_name)
    #run("sudo chmod o+w /var/www/%s/archive" % env.project_name)
    #run("sudo chmod o+w /var/www/%s/public_html/content" % env.project_name)
    #run("sudo chmod o+w /var/www/%s/public_html/img" % env.project_name)
    run("sudo chmod -R g+rwx %s" % get_fborm_folder())
    run("sudo chmod o+w %s" % get_fborm_folder())
    run("rm -f /var/www/%s/.git/deploy_bundle" % env.project_name)


@roles('dev')
def stage():
    branch = get_git_branch()
    local('git pull origin %s' % branch)
    local('git push origin %s' % branch)
    with cd('/var/www/%s/' % env.project_name):
        update_with_pull(branch)
        run("./fbmvc migrate latest")
    correct()


@roles('live')
def deploy():
    with cd('/var/www/%s/' % env.project_name):
        previous_head = update_with_pull('live')
        puts("Previous live HEAD: %s" % previous_head)
        update_with_pull('live')
        run("./fbmvc migrate latest")


@roles('live')
def rollback(rev):
    with cd('/var/www/%s/' % env.project_name):
        run("git checkout '%s'" % rev)
