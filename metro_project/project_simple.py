# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.osv import fields,osv
from openerp.addons.base_status.base_stage import base_stage
from openerp.tools.translate import _
'''
1.Add 'type' field to extend the project's usage
2.Project can not be closed if there are opening tasks 
'''
class project_project(osv.osv):
    _inherit = 'project.project'
    _order = 'id desc'
    _columns = {
        'project_type': fields.selection([('simple','Simple'),('software','Software'),('engineer','Engineering'),('gtd','GTD')],string='Type',),
    }
    _defaults = {'project_type':'simple'}
    def set_done(self, cr, uid, ids, context=None):        
        if isinstance(ids, (int,long)):
            ids = [ids]
        if context == None:
            context = {}
        #the BOM is required when do project done
        for proj in self.browse(cr, uid, ids, context=context):
            for task in proj.tasks:
                if task.state != 'done':
                    raise osv.except_osv(_('Error!'), _('Project "%s" can not be close, the task "%s" is opening.'%(proj.name,task.name)))
        resu = super(project_project,self).set_done(cr, uid, ids, context) 
        return resu   
'''
1.Sending email to the assignee when creating and writing
'''    
class project_task(base_stage, osv.osv):
    _inherit = "project.task"    
    _columns = {
        'project_type': fields.related('project_id', 'project_type', type='selection', 
                                       selection=[('','Simple'),('simple','Simple'),('software','Software'),('engineer','Engineering')], 
                                       string='Project Type', select=1),
    }
    def email_send(self, cr, uid, ids, vals, context=None):
        email_tmpl_obj = self.pool.get('email.template')
        #send email to assignee
        if 'user_id' in vals:
            tmpl_ids = self.pool.get('email.template').search(cr, uid, [('name','=','project_task_assignee')])
            if tmpl_ids:
                for id in ids:
                    email_tmpl_obj.send_mail(cr, uid, tmpl_ids[0], id, force_send=True, context=context)
        return True
    
    def create(self, cr, uid, vals, context=None):
        new_id = super(project_task,self).create(cr, uid, vals ,context)
        self.email_send(cr, uid, [new_id],vals,context)
        return new_id
            
    def write(self, cr, uid, ids, vals, context=None):
        resu = super(project_task,self).write(cr, uid, ids, vals ,context)
        self.email_send(cr, uid, ids,vals,context)
        return resu     
    
    def fields_get(self, cr, uid, allfields=None, context=None, write_access=True):
        resu = super(project_task,self).fields_get(cr, uid, allfields,context,write_access)
        #set  the 'project_id' domain dynamically by the default_project_type
        default_project_type = context and context.get('default_project_type', False) or False
        if resu.has_key('project_id') and default_project_type:            
            project_ids = self.pool.get('project.project').search(cr, uid, [('project_type','=',default_project_type)], context=context)
            resu['project_id']['domain'] = [('id','in',project_ids)]
        return resu           