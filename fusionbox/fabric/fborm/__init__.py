from fabric.api import run, puts, cd

from fusionbox.fabric import fb_env
from fusionbox.fabric.git import get_git_branch
from fusionbox.fabric.update import get_update_function


def get_fborm_folder():
    """
    Gets the location of the fborm folder on the dev server.
    """
    branch = get_git_branch()
    return '{0}/fborm{1}/'.format(
        fb_env.dev_web_home,
        '' if branch == 'master' else ':' + branch,
    )


def correct():
    """
    Resets permissions on dev site files to avoid errors.

    NOTE: This is a hack...there I said it.
    """
    run('sudo chgrp -R fusionbox /var/www/%s' % fb_env.dev_project_dir)
    run('sudo chmod -R g+rwx /var/www/%s' % fb_env.dev_project_dir)
    run('sudo chmod -R g+rwx %s' % get_fborm_folder())
    run('sudo chmod o+w %s' % get_fborm_folder())


def stage(branch=None, role='dev'):
    """
    Updates the remote site files to your local branch head and migrates.
    """
    update_function = get_update_function()
    branch = branch or get_git_branch()

    project_loc = fb_env.role(role, 'project_loc')

    with cd(project_loc):
        previous_head = update_function(branch)
        puts('Previous remote HEAD: {0}'.format(previous_head))
        run('./fbmvc dbdump')
        run('./fbmvc migrate latest')

    if role == 'dev':
        correct()


def deploy():
    """
    Same as stage, but always uses the live branch and live config settings.
    """
    stage(branch='live', role='live')
