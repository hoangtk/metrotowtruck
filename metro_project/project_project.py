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
from lxml import etree
class project_project(osv.osv):
    _inherit = 'project.project'
    _columns = {
        'mfg_ids': fields.many2many('sale.product', 'project_id_rel','project_id','mfg_id',string='MFG IDs',),
        'bom_id': fields.many2one('mrp.bom', string='Bill of Material',),
        'product_id': fields.related('bom_id', 'product_id', type='many2one', relation='product.product', string='Product', readonly=True),
        'components': fields.related('bom_id', 'bom_lines', type='one2many', relation='mrp.bom', fields_id='bom_id', string='Components', readonly=True)
    }
    
class project_task(base_stage, osv.osv):
    _inherit = "project.task"
    _columns = {
        'project_bom_id': fields.related('project_id','bom_id',type='integer',string='Project BOM'),
        'bom_id': fields.many2one('mrp.bom', string='Bill of Material',domain="[('bom_id','=',project_id)]"),
        'product_id': fields.related('bom_id', 'product_id', type='many2one', relation='product.product', string='Product', readonly=True),
        'components': fields.related('bom_id', 'bom_lines', type='one2many', relation='mrp.bom', fields_id='bom_id', string='Components', readonly=True)
    }
#    def onchange_project(self, cr, uid, id, project_id):
#        value = super(project_task, self).onchange_project(cr, uid, id, project_id)
#        if project_id:
#            project = self.pool.get('project.project').browse(cr, uid, project_id)
#            members = []            
#            for m in project.members:
#                members.append(m.id)
#            if project:
#                value.update({'domain': {'user_id':[('id','in',members)]}})
#        return value  

    
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
#                   