from fabric.api import run, cd, puts

from fusionbox.fabric import fb_env
from fusionbox.fabric.git import get_git_branch
from fusionbox.fabric.update import get_update_function


def stage(branch=None, role='dev'):
    """
    Updates the remote site files to your local branch head.
    """
    update_function = get_update_function()
    branch = branch or get_git_branch()

    project_path = fb_env.role(role, 'project_path')

    with cd(project_path):
        previous_head = update_function(branch)
        puts('Previous remote HEAD: {0}'.format(previous_head))


def deploy():
    """
    Same as stage, but always uses the live branch and live config settings.
    """
    stage(branch='live', role='live')


def shell():
    """
    Fires up a shell on the live server.
    """
    with cd(fb_env.live_project_path):
        run('bash -')
