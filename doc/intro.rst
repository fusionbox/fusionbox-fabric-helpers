Introduction
============

Fabric helpers used by the development team at Fusionbox_ for server deployment.

Here is a minimal ``fabfile.py``::

    from fabric.api import env, roles
    
    from fusionbox.fabric.django import stage
    
    env.project_name = 'project'
    env.project_abbr = 'project'
    env.short_name = 'project'
    
    stage = roles('dev')(stage)


.. _Fusionbox: http://www.fusionbox.com
