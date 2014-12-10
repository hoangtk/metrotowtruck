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
from lxml import etree
from dateutil import rrule
from datetime import datetime, timedelta
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.misc import DEFAULT_SERVER_DATE_FORMAT
from openerp.addons.metro import utils

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp import netsvc
'''
Attendance monthly report
'''
class hr_rpt_attend_month(osv.osv):
    _name = "hr.rpt.attend.month"
    _description = "HR Attendance monthly report"
    _inherit = ['mail.thread']
    _columns = {
        'name': fields.char('Report Name', size=16, required=False),
        'title': fields.char('Report Title', required=False),
        'type': fields.char('Report Type', size=16, required=True),
        'company_id': fields.many2one('res.company','Company',required=True),  
        
        #report data lines
        'rpt_lines': fields.one2many('hr.rpt.attend.month.line', 'rpt_id', string='Report Line'),
        'date_from': fields.datetime("Start Date", required=True),
        'date_to': fields.datetime("End Date", required=True),
        'emp_ids': fields.many2many('hr.employee', string='Employees'),
        
        'state': fields.selection([
            ('draft', 'Draft'),
            ('confirmed', 'Waiting Approve'),
            ('done', 'Done'),
            ('rejected', 'Rejected'),
            ('cancel', 'Cancel'),
        ], 'Status', select=True, readonly=True, track_visibility='onchange', 
            help='* When the report is created the status is \'Draft\'.\
            \n* If the payslip is confirmed, the status is \'Waiting Approve\'. \
            \n* If the payslip is approved then status is set to \'Done\'.\
            \n* If the payslip is rejected then status is set to \'Rejected\'.\
            \n* When user cancel payslip the status is \'Cancel\'.'),        
    
        'note': fields.text('Description', readonly=False, states={'done':[('readonly',True)]}),
        }

    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.rptcn', context=c),
        'type': 'attend_month',   
        'state': 'draft',  
#        'emp_ids':[342,171]
    }
    def default_get(self, cr, uid, fields, context=None):
        vals = super(hr_rpt_attend_month, self).default_get(cr, uid, fields, context=context)
        if 'date_from' in fields:
            #For the datetime value in defaults, need convert the local time to UTC, the web framework will convert them back to local time on GUI
            date_from =datetime.strptime(time.strftime('%Y-%m-01 00:00:00'), '%Y-%m-%d %H:%M:%S')
            date_from_utc = utils.utc_timestamp(cr, uid, date_from, context)
            vals.update({'date_from':date_from_utc.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                         
        if 'date_to' in fields:
            date_to = datetime.strptime(time.strftime('%Y-%m-%d 23:59:59'), '%Y-%m-%d %H:%M:%S')        
            date_to_utc = utils.utc_timestamp(cr, uid, date_to, context)        
            vals.update({'date_to':date_to_utc.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})

        #set default title by i18n
        if context.get('default_title',False):
            vals['title'] = _(context.get('default_title'))        
    
        return vals
                
    def _check_dates(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                return False
        return True

    _constraints = [
        (_check_dates, 'The date end must be after the date start.', ['date_from','date_to']),
    ]
    
    def wkf_confirm(self, cr, uid, ids, context=None):
        for rpt in self.browse(cr, uid, ids, context=context):
            if not rpt.rpt_lines:
                raise osv.except_osv(_('Error!'),_('No attendance data, can not confirm, please generate attendance first!'))
        self.write(cr, uid, ids, {'state':'confirmed'}, context=context)
        return True
    
    def wkf_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cancel'}, context=context)
        return True
    
    def action_done_cancel(self, cr, uid, ids, context=None):
        if not len(ids):
            return False        
        #update status
        self.wkf_cancel(cr, uid, ids, context=context)
        wf_service = netsvc.LocalService("workflow")
        #recrate workflow and do draft-->cancel
        for p_id in ids:
            # Deleting the existing instance of workflow for PO
            wf_service.trg_delete(uid, 'hr.rpt.attend.month', p_id, cr)
            wf_service.trg_create(uid, 'hr.rpt.attend.month', p_id, cr)
            wf_service.trg_validate(uid, 'hr.rpt.attend.month', p_id, 'cancel', cr)
        return True
        
    def action_cancel_draft(self, cr, uid, ids, context=None):
        if not len(ids):
            return False
        self.write(cr, uid, ids, {'state':'draft'})
        wf_service = netsvc.LocalService("workflow")
        for p_id in ids:
            # Deleting the existing instance of workflow for PO
            wf_service.trg_delete(uid, 'hr.rpt.attend.month', p_id, cr)
            wf_service.trg_create(uid, 'hr.rpt.attend.month', p_id, cr)
        return True
    
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        return "Attendance Monthly Report"
            
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if isinstance(ids,(int,long)):
            ids = [ids]
        res = []
        for row in self.read(cr, uid, ids, ['name'], context=context):
            res.append((row['id'],'[%s]%s'%(row['id'],row['name']) ))
        return res
    def _convert_save_dates(self, cr, uid, vals, context):
        #convert to the date like '2013-01-01' to UTC datetime to store
        if 'date_from' in vals and len(vals['date_from']) == 10:
            date_from = vals['date_from']
            date_from = utils.utc_timestamp(cr, uid, datetime.strptime(date_from + ' 00:00:00', DEFAULT_SERVER_DATETIME_FORMAT),context=context)
            date_from = date_from.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            vals['date_from'] = date_from
        if 'date_to' in vals and len(vals['date_to']) == 10:
            date_to = vals['date_to']
            date_to = utils.utc_timestamp(cr, uid, datetime.strptime(date_to + ' 23:59:59', DEFAULT_SERVER_DATETIME_FORMAT),context=context)
            date_to = date_to.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            vals['date_to'] = date_to
            
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['rpt_lines'] = None
        return super(hr_rpt_attend_month, self).copy(cr, uid, id, default, context)
    
    def create(self, cr, uid, vals, context=None):
        if 'name' not in vals or not vals['name']:
            date_from = datetime.strptime(vals['date_to'], DEFAULT_SERVER_DATETIME_FORMAT)
            name = '%s-%s'%(date_from.year, date_from.month)
            vals['name'] = name
        self._convert_save_dates(cr, uid, vals, context)
        id_new = super(hr_rpt_attend_month, self).create(cr, uid, vals, context=context)
        return id_new
    
    def write(self, cr, uid, ids, vals, context=None):
        self._convert_save_dates(cr, uid, vals, context)
        resu = super(hr_rpt_attend_month, self).write(cr, uid, ids, vals, context=context)
        return resu
    
    def unlink(self, cr, uid, ids, context=None):
        for rpt in self.read(cr, uid, ids, ['state'], context=context):
            if rpt['state'] not in ('draft','cancel'):
                raise osv.except_osv(_('Error'),_('Only order with Draft/Cancel state can be delete!'))
        return super(hr_rpt_attend_month, self).unlink(cr, uid, ids, context=context)
    
    def run_report(self, cr, uid, ids, context=None):
        rpt = self.browse(cr, uid, ids, context=context)[0]
        if not rpt.emp_ids:
            raise osv.except_osv(_('Warning!'),_('Please select employees to get attendance!'))
        rpt_method = getattr(self, 'run_%s'%(rpt.type,))
        #get report data
        rpt_line_obj,  rpt_lns = rpt_method(cr, uid, ids, context)
        #remove the old lines
        unlink_ids = rpt_line_obj.search(cr, uid, [('rpt_id','=',rpt.id)], context=context)
        rpt_line_obj.unlink(cr ,uid, unlink_ids, context=context)
        #create new lines
        for rpt_line in rpt_lns:
            rpt_line['rpt_id'] = rpt.id
            rpt_line_obj.create(cr ,uid, rpt_line, context=context)  
        return True
    
    def run_attend_month(self, cr, uid, ids, context=None):
        '''
        1.Call hr_rpt_attend_emp_day.run_attend_emp_day() to get all detail data
        '''
        rpt = self.browse(cr, uid, ids, context=context)[0]
        rpt_dtl_obj = self.pool.get('hr.rpt.attend.emp.day')
        rpt_dtl_vals = {'date_from':rpt.date_from, 'date_to':rpt.date_to, 'emp_ids':[(4,emp.id) for emp in rpt.emp_ids]}
        rpt_dtl_id = rpt_dtl_obj.create(cr, uid, rpt_dtl_vals, context=context)
        rpt_dtl_lines = rpt_dtl_obj.run_attend_emp_day(cr, uid, [rpt_dtl_id], context=context)[1]
        ''''
        2.Sum data by the detail
        '''
        date_from = datetime.strptime(rpt.date_from,DEFAULT_SERVER_DATETIME_FORMAT)
        date_to = datetime.strptime(rpt.date_to,DEFAULT_SERVER_DATETIME_FORMAT)
        date_from_local = fields.datetime.context_timestamp(cr, uid, date_from, context)
        date_to_local = fields.datetime.context_timestamp(cr, uid, date_to, context)
        days = rrule.rrule(rrule.DAILY, dtstart=date_from_local,until=date_to_local)
        #the working days counting, normal and in law
        days_work = 0.0
        days_work2 = 0.0
        for day in days:
            if day.isoweekday() not in (6,7):
                days_work2 += 1       
            if day.isoweekday() != 7:
                days_work += 1
        #month attend days in law
        month_attend_days_law = rpt.company_id.month_attend_days_law
        #the employee details by emp_id
        emp_dtls = {}
        for rpt_dtl_line in rpt_dtl_lines:
            emp_dtl = emp_dtls.get(rpt_dtl_line['emp_id'],[])
            if not emp_dtl:
                emp_dtls[rpt_dtl_line['emp_id']] = emp_dtl
            emp_dtl.append(rpt_dtl_line)
        seq = 0
        work_periods = {}
        #report data line
        rpt_lns = []        
        emp_ids = rpt.emp_ids
        if not emp_ids:
            emp_obj = self.pool.get('hr.employee')
            emp_ids = emp_obj.search(cr, uid, [], context=context) 
            emp_ids = emp_obj.browse(cr, uid, emp_ids, context=context)       
        for emp in emp_ids:
            emp_dtl = emp_dtls.get(emp.id,[])
            days_attend = 0.0
            hours_ot = 0.0
            days_attend2 = 0.0
            hours_ot2_nonwe = 0.0
            hours_ot2_we = 0.0
            for dtl_line in emp_dtl:
                #get the work period object
                work_period = work_periods.get(dtl_line['period_id'], False)
                if not work_period:
                    work_period = self.pool.get('resource.calendar.attendance').browse(cr, uid, dtl_line['period_id'], context=context)
                    work_periods[dtl_line['period_id']] = work_period
                #days
                if dtl_line['hours_normal'] and work_period.hours_work_normal != 0:
                        days_attend += dtl_line['hours_normal']/work_period.hours_work_normal*work_period.days_work
                if dtl_line['hours_ot']:
                    hours_ot += dtl_line['hours_ot']
                #days2       
                if dtl_line['hours_normal2'] and work_period.hours_work_normal2 != 0:
                        days_attend2 += dtl_line['hours_normal2']/work_period.hours_work_normal2*work_period.days_work2
                if dtl_line['hours_ot2']:
                    if work_period.dayofweek in('5','6'):
                        hours_ot2_we += dtl_line['hours_ot2']
                    else:
                        hours_ot2_nonwe += dtl_line['hours_ot2']
            if days_work2 != 0:            
                days_attend2 = days_attend2/days_work2*month_attend_days_law

            seq += 1
            rpt_line = {'seq': seq,
                            'code': emp.code,
                            'name': emp.name,
                            'emp_id': emp.id,
                            'days_work':days_work,
                            'days_attend': days_attend,
                            'hours_ot':hours_ot,
                            'days_work2':days_work2,
                            'days_attend2':days_attend2,
                            'hours_ot2_nonwe':hours_ot2_nonwe,
                            'hours_ot2_we':hours_ot2_we}
            rpt_lns.append(rpt_line)
        '''========return data to rpt_base.run_report()========='''    
        return self.pool.get('hr.rpt.attend.month.line'), rpt_lns
    
    def _pdf_data(self, cr, uid, ids, form_data, context=None):
        return {'xmlrpt_name': 'hr.rpt.attend.month'}
    
    def save_pdf(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids[0], context=context)
        rptxml_name = self._pdf_data(cr, uid, ids[0], form_data, context=context)['xmlrpt_name']
        datas = {
                 'model': self._name,
                 'ids': [ids[0]],
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': rptxml_name, 'datas': datas, 'nodestroy': True}    
        
hr_rpt_attend_month()

class hr_rpt_attend_month_line(osv.osv):
    _name = "hr.rpt.attend.month.line"
    _description = "HR Attendance Monthly Report Lines"
    _order = 'seq'
    _columns = {
        'code': fields.char('Code', size=64, ),
        'name': fields.char('Name', size=256, ),
        'data_level': fields.char('Data level code', size=64),
        
        'rpt_id': fields.many2one('hr.rpt.attend.month', 'Report'),
        'seq': fields.integer('Sequence',),
        'emp_id': fields.many2one('hr.employee', 'Employee',),
        'emp_code': fields.related('emp_id','emp_code',string='Code', type='char'),
        'emp_name': fields.related('emp_id','name',string='Name', type='char'),
        
        'days_work': fields.float('Days'),
        'days_attend': fields.float('Days Attended'),
        'hours_ot': fields.float('Hours OT'),
        'days_work2': fields.float('Days2'),
        'days_attend2': fields.float('Days Attended2'),
        'hours_ot2_nonwe': fields.float('Hours OT2 Non Weekend'),
        'hours_ot2_we': fields.float('Hours OT2 Weekend'),
    }

hr_rpt_attend_month_line()

from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext
report_sxw.report_sxw('report.hr.rpt.attend.month', 'hr.rpt.attend.month', 'addons/metro_hr/wizard/hr_rpt_attend_month.rml', parser=rml_parser_ext, header='internal')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
