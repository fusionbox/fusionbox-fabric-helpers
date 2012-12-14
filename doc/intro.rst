Introduction
============

Fabric helpers used by the development team at Fusionbox_ for server deployment.

Here is a minimal ``fabfile.py``::

    from fabric.api import env, roles

    from fusionbox.fabric import fb_env
    from fusionbox.fabric.django import stage, deploy

    env.roledefs['live'] = ['cowboyneal@foobar.com']

    fb_env.project_name = 'foobar'

    stage = roles('dev')(stage)
    deploy = roles('live')(deploy)

In the case that either the live or dev host has a unique config that is
different from the default (such as with webfaction), a fabfile something like
this may be used::

    from fabric.api import env, roles

    from fusionbox.fabric import fb_env
    from fusionbox.fabric.django import stage, deploy

    env.roledefs['live'] = ['cowboyneal@foobar.com']

    fb_env.project_name = 'foobar'
    fb_env.live_web_home = '/home/cowboyneal/webapps'
    fb_env.live_workon_home = '/home/cowboyneal/virtualenvs'

    stage = roles('dev')(stage)
    deploy = roles('live')(deploy)


.. _Fusionbox: http://www.fusionbox.com
