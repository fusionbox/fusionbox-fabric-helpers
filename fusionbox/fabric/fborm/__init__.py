from fabric.api import run, local, puts, cd

from fusionbox.fabric import get_git_branch, get_update_function, fb_env


def get_fborm_folder():
    branch = get_git_branch()
    return '/var/www/fborm%s/' % ("" if branch == "master" else ":" + branch)


def correct():
    run("sudo chgrp -R fusionbox /var/www/%s" % fb_env.project_name)
    run("sudo chmod -R g+rwx /var/www/%s" % fb_env.project_name)
    #run("sudo chmod o+w /var/www/%s/archive" % fb_env.project_name)
    #run("sudo chmod o+w /var/www/%s/public_html/content" % fb_env.project_name)
    #run("sudo chmod o+w /var/www/%s/public_html/img" % fb_env.project_name)
    run("sudo chmod -R g+rwx %s" % get_fborm_folder())
    run("sudo chmod o+w %s" % get_fborm_folder())


def stage():
    update_function = get_update_function()
    branch = get_git_branch()

    local('git pull origin %s' % branch)
    local('git push origin %s' % branch)

    with cd('/var/www/%s/' % fb_env.project_name):
        update_function(branch)
        run("./fbmvc migrate latest")

    correct()


def deploy():
    update_function = get_update_function()

    with cd('/var/www/%s/' % fb_env.project_name):
        previous_head = update_function('live')
        puts("Previous live HEAD: %s" % previous_head)
        run("./fbmvc migrate latest")


def rollback(rev):
    with cd('/var/www/%s/' % fb_env.project_name):
        run("git checkout '%s'" % rev)
