# -*- coding: utf-8 -*-
'''
Created on 2014-1-8

@author: john.wang
'''
from osv import fields, osv
from tools.translate import _

class email_template(osv.Model):
    _inherit = 'email.template'
    _sql_constraints = [
        ('name', 'unique (name)', _('Email Template Name must be unique!'))
    ]     