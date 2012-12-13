Introduction
============

Fabric helpers used by the development team at Fusionbox_ for server deployment.

Here is a minimal ``fabfile.py``::

    from fabric.api import env, roles
    
    from fusionbox.fabric.django import stage
    
    env.project_name = 'rjandmakay'
    env.project_abbr = 'rjandmakay'
    env.short_name = 'rjandmakay'
    
    stage = roles('dev')(stage)


.. _Fusionbox: http://www.fusionbox.com
