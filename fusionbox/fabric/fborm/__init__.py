from fabric.api import run, local, puts, cd, env

from fusionbox.fabric.git_helpers import get_git_branch, update_with_git


def get_fborm_folder():
    branch = get_git_branch()
    return '/var/www/fborm%s/' % ("" if branch == "master" else ":" + branch)


def correct():
    run("sudo chgrp -R fusionbox /var/www/%s" % env.project_name)
    run("sudo chmod -R g+rwx /var/www/%s" % env.project_name)
    #run("sudo chmod o+w /var/www/%s/archive" % env.project_name)
    #run("sudo chmod o+w /var/www/%s/public_html/content" % env.project_name)
    #run("sudo chmod o+w /var/www/%s/public_html/img" % env.project_name)
    run("sudo chmod -R g+rwx %s" % get_fborm_folder())
    run("sudo chmod o+w %s" % get_fborm_folder())
    run("rm -f /var/www/%s/.git/deploy_bundle" % env.project_name)


def stage():
    branch = get_git_branch()
    local('git pull origin %s' % branch)
    local('git push origin %s' % branch)
    with cd('/var/www/%s/' % env.project_name):
        update_with_git(branch)
        run("./fbmvc migrate latest")
    correct()


def deploy():
    with cd('/var/www/%s/' % env.project_name):
        previous_head = update_with_git('live')
        puts("Previous live HEAD: %s" % previous_head)
        run("./fbmvc migrate latest")


def rollback(rev):
    with cd('/var/www/%s/' % env.project_name):
        run("git checkout '%s'" % rev)
