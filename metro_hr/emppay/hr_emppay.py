#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    d$
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

import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta

from openerp import netsvc
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from openerp.tools.safe_eval import safe_eval as eval

class hr_emppay_alwded(osv.osv):
    """
    Salary allowance and the deduction
    """

    _name = 'hr.emppay.alwded'
    _description = 'Salary allowance and the deduction'
    _order = 'type, sequence'
    _columns = {
        'sequence': fields.integer('#', required=True),
        'code':fields.char('Reference', size=64, required=True, select=True),
        'name':fields.char('Name', size=256, required=True, translate=True),
        'type':fields.selection([('alw','Allowance'),('ded','Deduction')], string='Type', required=True ),
        'type_calc':fields.selection([('fixed','Fixed'),('by_attend','By Attendance')], string='Calculation Type', required=True ),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'company_id':fields.many2one('res.company', 'Company', required=True),
    }
    
    _defaults={
               'type_calc':'fixed',
               'company_id':lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid,context=context).company_id.id,
               }


class hr_contract_alwded(osv.osv):
    """
    Contract's Salary allowance and the deduction
    """
    _name = 'hr.contract.alwded'
    _description = 'Contact Salary''s allowance and the deduction'
    _order = 'type, sequence'
    _columns = {
        'contract_id': fields.many2one('hr.contract',  'Contract', required=True, select=True),
        'alwded_id': fields.many2one('hr.emppay.alwded', 'Allowance/Deduction', required=True),
        'sequence': fields.related('alwded_id', 'sequence', type='integer', string='#', store=True, readonly=True),
        'type': fields.related('alwded_id', 'type', type='selection', selection=[('alw','Allowance'),('ded','Deduction')],
                                    string='Type', store=True, readonly=True),
        'type_calc':fields.related('alwded_id', 'type_calc', type='selection', selection=[('fixed','Fixed'),('by_attend','By Attendance')], 
                                    string='Calculation Type', store=True, readonly=True),
        #default is alwded_id.amount, user can change it
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
    }
    
    _defaults={
               'type_calc':'fixed',
               }
    def onchange_alwded_id(self, cr, uid, ids, alwded_id, context=None):
        alwded = self.pool.get('hr.emppay.alwded').browse(cr, uid, alwded_id, context=context)
        vals = {'sequence':alwded.sequence, 'type':alwded.type, 'type_calc':alwded.type_calc, 'amount':alwded.amount}
        return {'value':vals}
        
class hr_emppay_si(osv.osv):
    """
    Salary Social Insurance
    """
    _name = 'hr.emppay.si'
    _description = 'Salary Social Insurance'
    def _amount_all(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for si in self.browse(cr, uid, ids, context=context):
            if 'amount_company' in field_names:
                res[si.id]['amount_company'] = si.amount_base * si.rate_company/100.00
            if 'amount_personal' in field_names:
                res[si.id]['amount_personal'] = si.amount_base * si.rate_personal/100.00
        return res
    
    _columns = {
        'sequence': fields.integer('#', required=True, select=True),
        'code':fields.char('Reference', size=64, required=True),
        'name':fields.char('Name', size=256, required=True, translate=True),
        'amount_base':fields.float('Base Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_company':fields.float('Company Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_personal':fields.float('Personal Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'amount_company':fields.function(_amount_all, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
        'amount_personal':fields.function(_amount_all, string='Personal Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
        'company_id':fields.many2one('res.company', 'Company', required=True),
    }
    
    _defaults={
               'company_id':lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid,context=context).company_id.id,
               }    

class hr_contract_si(osv.osv):
    """
    Contract's Salary Social Insurance
    """
    _name = 'hr.contract.si'
    _description = 'Contact''s Salary Social Insurance'
    def _amount_all(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for si in self.browse(cr, uid, ids, context=context):
            if 'amount_company' in field_names:
                res[si.id]['amount_company'] = si.amount_base * si.rate_company
            if 'amount_personal' in field_names:
                res[si.id]['amount_personal'] = si.amount_base * si.rate_personal
        return res    
    
    _order = 'sequence'
    
    _columns = {
        'contract_id': fields.many2one('hr.contract', 'Contract', required=True, select=True),
        'si_id': fields.many2one('hr.emppay.si', 'Social Insurance', required=True),
        'sequence': fields.related('si_id', 'sequence', type='integer', string='#', store=True, readonly=True),
        #default get from hr_salary_si, user can change
        'amount_base':fields.float('Base Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_company':fields.float('Company Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_personal':fields.float('Personal Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'amount_company':fields.function(_amount_all, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
        'amount_personal':fields.function(_amount_all, string='Personal Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
    }
    def onchange_si_id(self, cr, uid, ids, si_id, context=None):
        si = self.pool.get('hr.emppay.si').browse(cr, uid, si_id, context=context)
        vals = {'sequence':si.sequence, 
                'amount_base':si.amount_base, 
                'rate_company':si.rate_company, 
                'rate_personal':si.rate_personal,
                'amount_company':si.amount_company, 
                'amount_personal':si.amount_personal}
        return {'value':vals}
    
class hr_contract(osv.osv):
    _inherit = 'hr.contract'
    
    def _amount_emppay(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for contract in self.browse(cr, uid, ids, context=context):
            #for ths SI data
            si_total_company = 0.0
            si_total_personal = 0.0
            for si in contract.si_ids:
                si_total_company += si.amount_company
                si_total_personal += si.amount_personal
            if 'si_total_company' in field_names:
                res[contract.id]['si_total_company'] = si_total_company
            if 'si_total_personal' in field_names:
                res[contract.id]['si_total_personal'] = si_total_personal
        return res
    
    def alwded_dict(self, cr, uid, contract_id, context=None):
        lines_alw = []
        lines_deb = []
        if not contract_id:
            return lines_alw, lines_deb
        contract = self.browse(cr, uid, contract_id, context=context)
        for item in contract.alwded_ids:
            line = {'sequence':item.sequence,
                    'code':item.alwded_id.code,
                    'name':item.alwded_id.name,
                    'type':item.type,
                    'type_calc':item.type_calc,
                    'amount':item.amount}
            if item.type == 'alw':
                lines_alw.append(line)
            else:
                lines_deb.append(line)
        return lines_alw, lines_deb 
        
    def si_dict(self, cr, uid, contract_id, context=None):
        lines = []
        if not contract_id:
            return lines
        contract = self.browse(cr, uid, contract_id, context=context)
        for item in contract.si_ids:
            line = {'sequence':item.sequence,
                    'code':item.si_id.code,
                    'name':item.si_id.name,
                    
                    'amount_base':item.amount_base,
                    'rate_company':item.rate_company,
                    'rate_personal':item.rate_personal,
                    'amount_company':item.amount_company,
                    'amount_personal':item.amount_personal,
                    }
            lines.append(line)
        return lines 
        
    _columns = {
        'alwded_ids': fields.one2many('hr.contract.alwded', 'contract_id', 'Allowance&Deduction'),
        'si_ids': fields.one2many('hr.contract.si', 'contract_id', 'Social Insurance'),
        'si_total_company':fields.function(_amount_emppay, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_emppay"),
        'si_total_personal':fields.function(_amount_emppay, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_emppay"),
        
        'wage2':fields.float('Wage2', digits_compute=dp.get_precision('Payroll')),
        'pit_base':fields.float('PIT Start Point', digits_compute=dp.get_precision('Payroll')),

    }
    def default_get(self, cr, uid, fields_list, context=None):
        defaults = super(hr_contract, self).default_get(cr, uid, fields_list, context=context)
        user_comp = self.pool.get('res.users').browse(cr, uid, uid,context=context).company_id
        defaults.update({'wage2':user_comp.emppay_wage2, 'pit_base':user_comp.emppay_pit_base})
        return defaults
        
    def get_contract(self, cr, uid, employee_id, date_from, date_to, context=None):
        """
        @param employee: browse record of employee
        @param date_from: date field
        @param date_to: date field
        @return: returns the ids of all the contracts for the given employee that need to be considered for the given dates
        """
        contract_obj = self.pool.get('hr.contract')
        #a contract is valid if it ends between the given dates
        clause_1 = ['&',('date_end', '<=', date_to),('date_end','>=', date_from)]
        #OR if it starts between the given dates
        clause_2 = ['&',('date_start', '<=', date_to),('date_start','>=', date_from)]
        #OR if it starts before the date_from and finish after the date_end (or never finish)
        clause_3 = [('date_start','<=', date_from),'|',('date_end', '=', False),('date_end','>=', date_to)]
        clause_final =  [('employee_id', '=', employee_id),'|','|'] + clause_1 + clause_2 + clause_3
        contract_ids = contract_obj.search(cr, uid, clause_final, context=context)
        return contract_ids    
    
class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        'emppay_wage2':fields.float('Wage2', digits_compute=dp.get_precision('Payroll')),
        'emppay_pit_base':fields.float('PIT Start Point', digits_compute=dp.get_precision('Payroll')),
    }
    _defaults={'emppay_pit_base':3500}

class hr_rpt_attend_month(osv.osv):
    _inherit = 'hr.rpt.attend.month'
    _columns = {
        'emppay_sheet_ids': fields.one2many('hr.emppay.sheet', 'attend_month_id', string='Payroll'),
    }
    #generate a new payroll
    def new_payroll(self, cr, uid, attend_id, context=None):
        payroll_data = self._payroll_data(cr, uid, attend_id, context=context)
        payroll_obj = self.pool.get('hr.emppay.sheet')
        #convert to the format for one2many to save by dict
        emppay_ids = [(0,0,slip) for slip in payroll_data['emppay_ids']]
        payroll_data['emppay_ids'] = emppay_ids
        payroll_id = payroll_obj.create(cr, uid, payroll_data, context=context)
        return payroll_id
    
    #add data to exist payroll
    def add_payroll(self, cr, uid, attend_id, payroll_id, remove_old_slips = False, context=None):
        payroll_data = self._payroll_data(cr, uid, attend_id, context=context)
        payroll_obj = self.pool.get('hr.emppay.sheet')
        #remove slips data
        if remove_old_slips:
            payslip_obj = self.pool.get('hr.emppay')
            unlink_ids = payslip_obj.search(cr, uid, [('emppay_sheet_id','=',payroll_id)], context=context)
            payslip_obj.unlink(cr ,uid, unlink_ids, context=context)
        #convert to the format for one2many to save by dict
        emppay_ids = [(0,0,slip) for slip in payroll_data['emppay_ids']]
        payroll_data['emppay_ids'] = emppay_ids
        payroll_obj.write(cr, uid, [payroll_id], payroll_data, context=context)
        return True
        
    def _payroll_data(self, cr, uid, attend_id, payroll_id = False, context=None):
        if isinstance(attend_id, list):
            attend_id = attend_id[0]
        attend = self.browse(cr, uid, attend_id, context=context)
        #payroll data
        emppay_sheet = {'attend_month_id':attend.id,
                            'date_from':attend.date_from, 
                            'date_to':attend.date_to}
        #payslips
        date_from = attend.date_from
        date_to = attend.date_to
        slips = []
        contract_obj = self.pool.get('hr.contract')
        #loop to add slip lines
        for attend_line in attend.rpt_lines:
            emp_id = attend_line.emp_id.id
            contract_ids = contract_obj.get_contract(cr, uid, emp_id, date_from, date_to, context=context)
            if not contract_ids:
                continue
            contract_id = contract_ids[0]
            contract = contract_obj.browse(cr, uid, contract_id, context=context)
            slip_alws, slip_deds = contract_obj.alwded_dict(cr, uid, contract_id, context=context)
            slip_sis = contract_obj.si_dict(cr, uid, contract_id, context=context)
            slip = {'attend_id':attend_line.id,
                    'employee_id': emp_id,
                    'contract_id': contract.id,
                    'wage':contract.wage,
                    'wage2':contract.wage2,
                    #the allowance, deduction and sodical insurance
                    'alw_ids': [(0,0,item) for item in slip_alws],
                    'ded_ids': [(0,0,item) for item in slip_deds],
                    'si_ids': [(0,0,item) for item in slip_sis],

                    #Below from attend data, user can change, 数据为只读
#                    'days_work': attend_line.days_work,
#                    'days_attend': attend_line.days_attend,
#                    'hours_ot': attend_line.hours_ot,
#                    'hours_ot_we': 0,
#                    'hours_ot_holiday': 0,
                    #下面相关字段的显示使用组来限制
#                    'days_work2': attend_line.days_work2,
#                    'days_attend2': attend_line.days_attend2,
#                    'hours_ot2': attend_line.hours_ot2_nonwe,
#                    'hours_ot_we2': attend_line.hours_ot2_we,
#                    'hours_ot_holiday2': 0
                    }
            slips.append(slip)
        #set slips and return
        emppay_sheet['emppay_ids'] = slips
        return emppay_sheet
    
class hr_emppay_sheet(osv.osv):
    _name = 'hr.emppay.sheet'
    _description = 'Payroll'
    _columns = {
        'name': fields.char('Reference', size=64, required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('close', 'Close'),
        ], 'Status', select=True, readonly=True),
        'date_from': fields.date('Date From', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_to': fields.date('Date To', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'emppay_ids': fields.one2many('hr.emppay', 'emppay_sheet_id', 'Payslips', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'attend_month_id': fields.many2one('hr.rpt.attend.month', 'Attendance Report'),
        'note': fields.text('Description', readonly=True, states={'draft':[('readonly',False)]}),
    }
    _defaults = {
        'state': 'draft',
        'date_from': lambda *a: time.strftime('%Y-%m-01'),
        'date_to': lambda *a: str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10],
    }

    def create(self, cr, uid, values, context=None):
        if not 'name' in values or values['name'] == '':
            name = self.pool.get('ir.sequence').get(cr, uid, 'emppay.payroll')
            values['name'] = name
        new_id = super(hr_emppay_sheet,self).create(cr, uid, values, context=context)
        return new_id
    
    def action_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    def action_close(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'close'}, context=context)
    
    def add_from_att_report(self, cr, uid, ids, context=None):
        order = self.browse(cr,uid,ids[0],context=context)
        if not order.attend_month_id:
            raise osv.except_osv(_('Invalid Action!'), _('Please set the Attendance Report first.'))
        return self.pool.get('hr.rpt.attend.month').add_payroll(cr, uid, order.attend_month_id.id, ids[0], remove_old_slips = False, context=context)        
    
#    def add_from_att_record(self, cr, uid, ids, context=None):
#        return self.write(cr, uid, ids, {'state': 'close'}, context=context)        

hr_emppay_sheet()



class hr_emppay_ln_alwded(osv.osv):
    """
    Payslip's line of allowance or deduction
    Most same structure with hr_emppay_alwded
    The reason to use this structure is that if user did adjustion to the hr_emppay_alwded globally, the salary history data won't be affected
    """

    _name = 'hr.emppay.ln.alwded'
    _description = 'Salary allowance and the deduction'
    _order = 'type, sequence'
    _columns = {
        'emppay_id': fields.many2one('hr.emppay', 'Payslip', required=True, select=True),
        'sequence': fields.integer('#', required=True),
        'code':fields.char('Reference', size=64, required=True, select=True),
        'name':fields.char('Name', size=256, required=True, translate=True),
        'type':fields.selection([('alw','Allowance'),('ded','Deduction')], string='Type', required=True ),
        'type_calc':fields.selection([('fixed','Fixed'),('by_attend','By Attendance')], string='Calculation Type', required=True ),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
    }
    
    _defaults={
               'type_calc':'fixed',
               }
    

class hr_emppay_ln_si(osv.osv):
    """
    Payslip's line of Social Insurance
    Most same structure with hr_emppay_si
    The reason to use this structure is that if user did adjustion to the hr_emppay_si globally, the salary history data won't be affected
    """
    _name = 'hr.emppay.ln.si'
    _description = 'Salary Social Insurance'
    def _amount_all(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for si in self.browse(cr, uid, ids, context=context):
            if 'amount_company' in field_names:
                res[si.id]['amount_company'] = si.amount_base * si.rate_company/100.00
            if 'amount_personal' in field_names:
                res[si.id]['amount_personal'] = si.amount_base * si.rate_personal/100.00
        return res
    
    _columns = {
        'emppay_id': fields.many2one('hr.emppay', 'Payslip', required=True, select=True),
        'sequence': fields.integer('#', required=True, select=True),
        'code':fields.char('Reference', size=64, required=True),
        'name':fields.char('Name', size=256, required=True, translate=True),
        'amount_base':fields.float('Base Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_company':fields.float('Company Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_personal':fields.float('Personal Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'amount_company':fields.function(_amount_all, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
        'amount_personal':fields.function(_amount_all, string='Personal Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
    }
        
class hr_emppay(osv.osv):
    '''
    Pay Slip
    '''    
    _name = 'hr.emppay'
    _description = 'Pay Slip'

    _columns = {
        'name': fields.char('Reference', size=64, required=False, readonly=True, states={'draft': [('readonly', False)]}),   
        'date_from': fields.date('Date From', readonly=True, states={'draft': [('readonly', False)]}, required=True),
        'date_to': fields.date('Date To', readonly=True, states={'draft': [('readonly', False)]}, required=True),        
        'employee_id': fields.many2one('hr.employee', 'Employee', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'contract_id': fields.many2one('hr.contract', 'Contract', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        
        #Below from employee contract, 数据为只读
        #contract.wage
        'wage':fields.related('contract_id', 'wage', type="float", string='Wage', digits_compute=dp.get_precision('Payroll'), readonly=True),
        #contract.wage2
        'wage2':fields.related('contract_id', 'wage2', type="float", string='Wage2', digits_compute=dp.get_precision('Payroll'), readonly=True),     
        #attendance report line id
        'attend_id':fields.many2one('hr.rpt.attend.month.line', 'Attendance'),
        
        #Below from attend data, user can change, 数据为只读
        'days_work': fields.related('attend_id','days_work',type='float',string='Work Days'), #attend_line_id.days_work
        'days_attend': fields.related('attend_id','days_attend',type='float',string='Days Attended'),#attend_line_id.days_attend
        'hours_ot': fields.related('attend_id','hours_ot',type='float',string='Hours OT(Normal)'),#attend_line_id.hours_ot
        'hours_ot_we': fields.float('Hours OT(Week End)'),#0
        'hours_ot_holiday': fields.float('Hours OT(Law Holiday)'), #0
        #Below from attend data, user can change, 数据为只读, 下面相关字段的显示使用组来限制
        'days_work2': fields.related('attend_id','days_work2',type='float',string='Work Days'), #attend_line_id.days_work2
        'days_attend2': fields.related('attend_id','days_attend2',type='float',string='Days Attended'),#attend_line_id.days_attend2
        'hours_ot2': fields.related('attend_id','hours_ot2_nonwe',type='float',string='Hours OT(Normal)'),#attend_line_id.hours_ot2_nonwe
        'hours_ot_we2': fields.related('attend_id','hours_ot2_we',type='float',string='Hours OT(Week End)'),#attend_line_id.hours_ot2_we
        'hours_ot_holiday2': fields.float('Hours OT(Law Holiday)'), #0   
        
        'state': fields.selection([
            ('draft', 'Draft'),
            ('verify', 'Waiting'),
            ('done', 'Done'),
            ('cancel', 'Rejected'),
        ], 'Status', select=True, readonly=True,
            help='* When the payslip is created the status is \'Draft\'.\
            \n* If the payslip is under verification, the status is \'Waiting\'. \
            \n* If the payslip is confirmed then status is set to \'Done\'.\
            \n* When user cancel payslip the status is \'Rejected\'.'),
        'company_id': fields.many2one('res.company', 'Company', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'note': fields.text('Description', readonly=True, states={'draft':[('readonly',False)]}),
        'emppay_sheet_id': fields.many2one('hr.emppay.sheet', 'Payroll', readonly=True, states={'draft': [('readonly', False)]}),
        
        'alw_ids': fields.one2many('hr.emppay.ln.alwded', 'emppay_id', 'Allowance', required=False, readonly=True, 
                                   states={'draft': [('readonly', False)]}, domain=[('type','=','alw')]),
        'ded_ids': fields.one2many('hr.emppay.ln.alwded', 'emppay_id', 'Deduction', required=False, readonly=True, 
                                   states={'draft': [('readonly', False)]}, domain=[('type','=','ded')]),
        'si_ids': fields.one2many('hr.emppay.ln.si', 'emppay_id', 'Social Insurance', required=False, readonly=True, states={'draft': [('readonly', False)]}),
    }
    _defaults = {
        'date_from': lambda *a: time.strftime('%Y-%m-01'),
        'date_to': lambda *a: str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10],
        'state': 'draft',
        'company_id': lambda self, cr, uid, context: \
                self.pool.get('res.users').browse(cr, uid, uid,
                    context=context).company_id.id,
    }

    def _check_dates(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.date_from > payslip.date_to:
                return False
        return True

    _constraints = [(_check_dates, "Payslip 'Date From' must be before 'Date To'.", ['date_from', 'date_to'])]

    def create(self, cr, uid, values, context=None):
        if not 'name' in values or values['name'] == '':
            name = self.pool.get('ir.sequence').get(cr, uid, 'emppay.payslip')
            values['name'] = name
        return super(hr_emppay,self).create(cr, uid, values, context=context)
        
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'company_id': self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
            'name': self.pool.get('ir.sequence').get(cr, uid, 'emppay.payslip'),
            'emppay_sheet_id': False,
        })
        
        return super(hr_emppay, self).copy(cr, uid, id, default, context=context)

    def cancel_sheet(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

    def process_sheet(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'done'}, context=context)

    def hr_verify_sheet(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'verify'}, context=context)

    def check_done(self, cr, uid, ids, context=None):
        return True

    def unlink(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.state not in  ['draft','cancel']:
                raise osv.except_osv(_('Warning!'),_('You cannot delete a payslip which is not draft or cancelled!'))
        return super(hr_emppay, self).unlink(cr, uid, ids, context)
    
    def onchange_employee_id(self, cr, uid, ids, date_from, date_to, employee_id=False, contract_id=False, context=None):
        empolyee_obj = self.pool.get('hr.employee')
        contract_obj = self.pool.get('hr.contract')
        worked_days_obj = self.pool.get('hr.payslip.worked_days')
        input_obj = self.pool.get('hr.payslip.input')

        if context is None:
            context = {}
        #delete old worked days lines
        old_worked_days_ids = ids and worked_days_obj.search(cr, uid, [('payslip_id', '=', ids[0])], context=context) or False
        if old_worked_days_ids:
            worked_days_obj.unlink(cr, uid, old_worked_days_ids, context=context)

        #delete old input lines
        old_input_ids = ids and input_obj.search(cr, uid, [('payslip_id', '=', ids[0])], context=context) or False
        if old_input_ids:
            input_obj.unlink(cr, uid, old_input_ids, context=context)


        #defaults
        res = {'value':{
                      'line_ids':[],
                      'input_line_ids': [],
                      'worked_days_line_ids': [],
                      #'details_by_salary_head':[], TODO put me back
                      'name':'',
                      'contract_id': False,
                      'struct_id': False,
                      }
            }
        if (not employee_id) or (not date_from) or (not date_to):
            return res
        ttyme = datetime.fromtimestamp(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
        employee_id = empolyee_obj.browse(cr, uid, employee_id, context=context)
        res['value'].update({
                    'name': _('Salary Slip of %s for %s') % (employee_id.name, tools.ustr(ttyme.strftime('%B-%Y'))),
                    'company_id': employee_id.company_id.id
        })
        
        if not context.get('contract', False):
            #fill with the first contract of the employee
            contract_ids = self.pool.get('hr.contract').get_contract(cr, uid, employee_id.id, date_from, date_to, context=context)
        else:
            if contract_id:
                #set the list of contract for which the input have to be filled
                contract_ids = [contract_id]
            else:
                #if we don't give the contract, then the input to fill should be for all current contracts of the employee
                contract_ids = self.pool.get('hr.contract').get_contract(cr, uid, employee_id.id, date_from, date_to, context=context)

        if not contract_ids:
            return res
        contract_record = contract_obj.browse(cr, uid, contract_ids[0], context=context)
        res['value'].update({
                    'contract_id': contract_record and contract_record.id or False
        })
        struct_record = contract_record and contract_record.struct_id or False
        if not struct_record:
            return res
        res['value'].update({
                    'struct_id': struct_record.id,
        })
        #computation of the salary input
        worked_days_line_ids = self.get_worked_day_lines(cr, uid, contract_ids, date_from, date_to, context=context)
        input_line_ids = self.get_inputs(cr, uid, contract_ids, date_from, date_to, context=context)
        res['value'].update({
                    'worked_days_line_ids': worked_days_line_ids,
                    'input_line_ids': input_line_ids,
        })
        return res

    def onchange_contract_id(self, cr, uid, ids, date_from, date_to, employee_id=False, contract_id=False, context=None):
        #TODO it seems to be the mess in the onchanges, we should have onchange_employee => onchange_contract => doing all the things
        if context is None:
            context = {}
        res = {'value':{
                 'line_ids': [],
                 'name': '',
                 }
              }
        context.update({'contract': True})
        if not contract_id:
            res['value'].update({'struct_id': False})
        return self.onchange_employee_id(cr, uid, ids, date_from=date_from, date_to=date_to, employee_id=employee_id, contract_id=contract_id, context=context)

hr_emppay()

class hr_employee(osv.osv):
    '''
    Employee
    '''
    _inherit = 'hr.employee'
    _columns = {
        'emppay_ids':fields.one2many('hr.emppay', 'employee_id', 'Payslips', required=False, readonly=True)
    }

hr_employee()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
