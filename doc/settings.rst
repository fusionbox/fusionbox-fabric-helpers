Settings
========

Getting started
---------------

The `fusionbox-fabric-helpers` package exposes a configuration object called
`fb_env`.  The `fb_env` object allows one to customize the behavior of the
fabric helpers.  For example, the following fabfile uses the `fb_env` object to
set different configurations for the live and dev servers::

    from fabric.api import env, roles

    from fusionbox.fabric import fb_env
    from fusionbox.fabric.django import stage, deploy

    env.roledefs['live'] = ['foo@bar.com']

    fb_env.project_name = 'bar'

    fb_env.dev_web_home = '/var/www'
    fb_env.dev_workon_home = '/var/python-environments'

    fb_env.live_web_home = '/home/foo/webapps'
    fb_env.live_workon_home = '/home/foo/virtualenvs'

    stage = roles('dev')(stage)
    deploy = roles('live')(deploy)

This fabfile shows that, on the dev server, the project root directory is
located in `/var/www` and python virtual environments are located in
`/var/python-environments`.  On the live server, those resources are located in
`/home/foo/webapps` and `/home/foo/virtualenvs` respectively.

Other things are also happening behind the scenes.  The `project_name` setting
is used to build the absolute path to the project directory on the dev and live
servers as follows::

    path on dev:  /var/www/bar.com
    path on live: /home/foo/webapps/bar.com
    
The `project_name` is also automatically (not automagically!!) used to build
the paths to the python virtual environment::

    paths on dev:  /var/python-environments/bar
    paths on live: /home/foo/virtualenvs/bar

Any setting which is generated automatically can be manually overridden.  If
you wanted to manually set the absolute paths to the project, you could do
this::

    fb_env.dev_project_loc = '/var/www/weirdbar.com'
    fb_env.live_project_loc = '/home/foo/webapps/unweirdbar.com'
