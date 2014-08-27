# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
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

import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _

class task_group(osv.osv_memory):
    _name = "task.group"
    _columns = {
        'name': fields.char('Group', size=64, required=True),
#        'group_task_ids': fields.one2many('task.group.tasks','group_id','Group Tasks')
        'task_ids': fields.many2many('project.task','task_group_tasks','group_id','task_id',string='Group Tasks'),
        'task_day': fields.date('Day', ),
    }
class task_print(osv.osv_memory):
    _name = "task.print"
    _columns = {
        'task_day': fields.date('Day', ),
        'print_type': fields.selection([('by_assignee','Task List By Assignee'),('by_employee','Task List By Employee'),('by_team','Task List By Team')],'Type', required=True, select=False),
    }
    _defaults = {'print_type':'by_assignee'}
    
    def _get_assignee_name(self, cr, uid, task, context=None):
        return task.user_id.name
    
    def _get_emps_name(self, cr, uid, task, context=None):
        resu = 'No Employee'
        if task.emp_ids:
            resu = ''
            for emp in task.emp_ids:
                resu += (resu != '' and ',' or '') + emp.name
        return resu
    
    def _get_team_name(self, cr, uid, task, context=None):
        dept_name = 'No Team'
        if task.dept_id:
            dept_name = task.dept_id.name    
        return dept_name
    
    def do_print(self, cr, uid, ids, context=None):
        if context is None:
            context = {}    
        active_ids = context and context.get('active_ids', [])
        data = self.browse(cr, uid, ids, context=context)[0]
        #set the group field name and function to get related name
        group_name_func = None
        if data.print_type == 'by_assignee':
            group_name_func = self._get_assignee_name
        elif data.print_type == 'by_employee':
            group_name_func = self._get_emps_name
        elif data.print_type == 'by_team':
            group_name_func = self._get_team_name
        #get the tasks by day
        task_day = ''
        if data.task_day:
            domain_day = ['|',('date_start','=',False),('date_start','<=', data.task_day + ' 23:59:59'),'|',('date_end','=',False),('date_end','>=', data.task_day + ' 00:00:00')]
            domain_day += [('state','!=','cancelled')]
            active_ids = self.pool.get('project.task').search(cr, uid, domain_day, context=context)
            task_day = data.task_day
        #get the group data
        groups = {}
        for task in self.pool.get('project.task').browse(cr, uid, active_ids, context=context):
            group_name = group_name_func(cr, uid, task, context)
            if not groups.get(group_name):
                groups.update({group_name:[]})
            groups.get(group_name).append((4,task.id))
        #create group data
        task_group_obj = self.pool.get('task.group')
        group_ids = []
        for group_name,tasks in groups.items():
            vals = {'name':group_name,'task_ids':tasks}
            if task_day:
                vals.update({'task_day':task_day})
            group_ids.append(task_group_obj.create(cr, uid, vals, context=context))
        #print tasks by group
        if not group_ids:
            return {'type': 'ir.actions.act_window_close'}     
        datas = {
                 'model': 'task.group',
                 'ids': group_ids,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'task.group.%s'%(data.print_type,), 'datas': datas, 'nodestroy': True}        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
