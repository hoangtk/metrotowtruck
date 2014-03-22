# -*- coding: utf-8 -*-

{
    'name': 'Metro',
    'version': '1.0',
    'category': 'Metro',
    "sequence": 14,
    'complexity': "easy",
    'description': """
    
        This module contains the common configurations needed by group of 
        Metro Modules.
    
    """,
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ['base','email_template'],
    'init_xml': [],
    'data' : [
       "ir_actions_view.xml",
       "metro_menu.xml",
	   "security/metro.xml",
       "order_informer.xml",
       "cron_job_data.xml",
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    #web
    "js": ["static/src/js/metro.js"],
    'qweb' : ["static/src/xml/lang_switch.xml"],
    'css' : ["static/src/css/lang_switch.css",
             "static/src/css/metro.css",],    
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
