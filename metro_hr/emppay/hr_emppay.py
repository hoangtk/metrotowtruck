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
    
    def _alwded_field_get(self, cr, uid, context=None):
        mf = self.pool.get('ir.model.fields')
        ids = mf.search(cr, uid, [('model','=', 'hr.rpt.attend.month.line'), ('ttype','=','float'), '|', ('name','like','alw_%'), ('name','like','ded_%')], context=context)
        res = []
        for field in mf.browse(cr, uid, ids, context=context):
            res.append((field.name, field.field_description))
        return res
    
    _columns = {
        'sequence': fields.integer('#', required=True),
        'code':fields.char('Reference', size=64, required=True, select=True),
        'name':fields.char('Name', size=256, required=True, translate=True),
        'type':fields.selection([('alw','Allowance'),('ded','Deduction')], string='Type', required=True ),
        'type_calc':fields.selection([('fixed','Fixed'),('by_attend','By Attendance')], string='Calculation Type', required=True ),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'company_id':fields.many2one('res.company', 'Company', required=True),
        #fields related to hr_rpt_attend_month_line
        "attend_field" : fields.selection(_alwded_field_get, "Attend Field", size=32, help="Associated field in the attendance report."),
    }
    
    _defaults={
               'type_calc':'fixed',
               'company_id':lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid,context=context).company_id.id,
               }
    _sql_constraints = [
        ('code_uniq', 'unique(code, type)', 'Name must be unique per Type!'),
    ]
    
    def write(self, cr, user, ids, vals, context=None):
        resu = super(hr_emppay_alwded, self).write(cr, user, ids, vals, context=context)
        '''
        Auto update the hr.contract.alwded data having same with current old data
        '''        
        #check if there are data that need sync to hr contract
        field_names = ['sequence', 'type', 'type_calc', 'amount', 'attend_field']
        field_names_deal = []
        for field_name in field_names:
            if field_name in vals:
                field_names_deal.append(field_name)
        #sync data to contract
        if field_names_deal:            
            contract_alwded_obj = self.pool.get('hr.contract.alwded')
            #field values will be update
            field_vals_upt = {}            
            for field_name in field_names_deal:
                field_vals_upt[field_name] = vals[field_name]
            #loop to update the data
            for id in ids:
                #old field values
                old_vals = self.read(cr, user, id, field_names_deal, context=context)
                #only the contract data that same with the alwded's old data will be update, if user changed the contract data, then do not update them automatically 
                field_names_domain = [('alwded_id', '=', id)]
                for field_name in field_names_deal:
                    field_names_domain.append((field_name, '=', old_vals[field_name]))
                upt_contract_alwded_ids = contract_alwded_obj.search(cr, user, field_names_domain, context=context)
                #do update
                if upt_contract_alwded_ids:
                    contract_alwded_obj.write(cr, user, upt_contract_alwded_ids,  field_vals_upt, context=context)
        
        return resu

class hr_contract_alwded(osv.osv):
    """
    Contract's Salary allowance and the deduction
    """
    _name = 'hr.contract.alwded'
    _description = 'Contact Salary''s allowance and the deduction'
    _order = 'type, sequence'
            
    def _alwded_field_get(self, cr, uid, context=None):
        mf = self.pool.get('ir.model.fields')
        ids = mf.search(cr, uid, [('model','=', 'hr.rpt.attend.month.line'), ('ttype','=','float'), '|', ('name','like','alw_%'), ('name','like','ded_%')], context=context)
        res = []
        for field in mf.browse(cr, uid, ids, context=context):
            res.append((field.name, field.field_description))
        return res
    
    _columns = {
        'contract_id': fields.many2one('hr.contract',  'Contract', required=True, select=True),
        'alwded_id': fields.many2one('hr.emppay.alwded', 'Allowance/Deduction', required=True),
        'sequence': fields.integer('#', required=True),
        'type':fields.selection([('alw','Allowance'),('ded','Deduction')], string='Type', required=True ),
        'type_calc':fields.selection([('fixed','Fixed'),('by_attend','By Attendance')], string='Calculation Type', required=True ),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        #fields related to hr_rpt_attend_month_line
        "attend_field" : fields.selection(_alwded_field_get, "Attend Field", size=32, help="Associated field in the attendance report."),
                
    }
    
    _defaults={
               'type_calc':'fixed',
               }
    def onchange_alwded_id(self, cr, uid, ids, alwded_id, context=None):
        alwded = self.pool.get('hr.emppay.alwded').browse(cr, uid, alwded_id, context=context)
        vals = {'sequence':alwded.sequence, 'type':alwded.type, 'type_calc':alwded.type_calc, 'amount':alwded.amount, 'attend_field':alwded.attend_field}
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


    def write(self, cr, user, ids, vals, context=None):
        resu = super(hr_emppay_si, self).write(cr, user, ids, vals, context=context)
        '''
        Auto update the hr.contract.si data having same with current old data
        '''
        #check if there are data that need sync to hr contract
        field_names = ['sequence', 'amount_base', 'rate_company', 'rate_personal']
        field_names_deal = []
        for field_name in field_names:
            if field_name in vals:
                field_names_deal.append(field_name)
        #sync data to contract
        if field_names_deal:            
            contract_si_obj = self.pool.get('hr.contract.si')
            #field values will be update
            field_vals_upt = {}            
            for field_name in field_names_deal:
                field_vals_upt[field_name] = vals[field_name]
            #loop to update the data
            for id in ids:
                #old field values
                old_vals = self.read(cr, user, id, field_names_deal, context=context)
                #only the contract data that same with the alwded's old data will be update, if user changed the contract data, then do not update them automatically 
                field_names_domain = [('alwded_id', '=', id)]
                for field_name in field_names_deal:
                    field_names_domain.append((field_name, '=', old_vals[field_name]))
                upt_contract_alwded_ids = contract_si_obj.search(cr, user, field_names_domain, context=context)
                #do update
                if upt_contract_alwded_ids:
                    contract_si_obj.write(cr, user, upt_contract_alwded_ids,  field_vals_upt, context=context)
        
        return resu
    
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
        'contract_id': fields.many2one('hr.contract', 'Contract', required=True, select=True, ondelete='cascade'),
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
                    'amount':item.amount,
                    'attend_field':item.attend_field}
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
        'emppay_sheet_ids': fields.one2many('hr.emppay.sheet', 'attend_month_id', string='Payroll', readonly=True),
    }
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['emppay_sheet_ids'] = None
        return super(hr_rpt_attend_month, self).copy(cr, uid, id, default, context)
    def wkf_cancel(self, cr, uid, ids, context=None):
        for rpt in self.browse(cr, uid, ids, context=context):
            if rpt.emppay_sheet_ids:
                for emppay_sheet in rpt.emppay_sheet_ids:
                    if emppay_sheet.state != 'cancel':
                        raise osv.except_osv(_('Error!'),_('There are related payrolls, please cancel or delete them first!'))
        return super(hr_rpt_attend_month, self).wkf_cancel(cr, uid, ids, context=context)
        
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
            slip_alws, slip_deds = self.emp_attend_alwded(cr, uid, attend_line, contract=contract, context=context)
            slip_sis = contract_obj.si_dict(cr, uid, contract_id, context=context)
            slip = {'attend_id':attend_line.id,
                    'employee_id': emp_id,
                    'contract_id': contract.id,
#                    18:22 wage/wage2 are changed to float already, do not use related fields now
#                    17:30 wage/wage2 are realted fields with store=True
#                    for the related fields with store=True, we need assign the value when creating by code,
#                    otherwise if the next code in same DB transaction can not get the data by browse(...),
#                    On this sample is the hr_emppay._wage_all() method can not get the wage/wage2 data
                    'wage':contract.wage,
                    'wage2':contract.wage2,
                    #the allowance, deduction and sodical insurance
                    'alw_ids': [(0,0,item) for item in slip_alws],
                    'ded_ids': [(0,0,item) for item in slip_deds],
                    'si_ids': [(0,0,item) for item in slip_sis],
                    
                    #Below fields are realted fields without store=True, so no need to assign, no the issue with wage/wage2 above
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
    
    def emp_attend_alwded(self, cr, uid, attend_line, contract=None, context=None):
        lines_alw = []
        lines_deb = []
        emp_id = attend_line.emp_id.id
        #get employee contract
        if not contract:
            contract_obj = self.pool.get('hr.contract')        
            contract_ids = contract_obj.get_contract(cr, uid, emp_id, attend_line.rpt_id.date_from, attend_line.rpt_id.date_to, context=context)
            if not contract_ids:
                return lines_alw, lines_deb
            contract_id = contract_ids[0]
            contract = contract_obj.browse(cr, uid, contract_id, context=context)
        #get allowance and deductions from contract
        for item in contract.alwded_ids:
            line = {'sequence':item.sequence,
                    'code':item.alwded_id.code,
                    'name':item.alwded_id.name,
                    'type':item.type,
                    'type_calc':item.type_calc,
                    'amount':item.amount,
                    'attend_field':item.attend_field}
            if item.type_calc == 'by_attend':
                if attend_line.days_work != 0:
                    line['amount'] = item['amount']*attend_line.days_attend/attend_line.days_work
                else:
                    line['amount'] = 0
            if item.type == 'alw':
                lines_alw.append(line)
            else:
                lines_deb.append(line)
        return lines_alw, lines_deb
    
    def emp_attend_alwded_by_field(self, cr, uid, attend_line, attend_fields, context=None):
        field_values = dict.fromkeys(attend_fields, 0)
        lines_alw, lines_deb = self.emp_attend_alwded(cr, uid, attend_line, context=context)
        lines_alwded = lines_alw + lines_deb
        for alwded in lines_alwded:
            field_name = alwded['attend_field']
            if field_name and field_name in attend_fields:
                field_values[field_name] = alwded['amount']
        return field_values
                    
class hr_emppay_sheet(osv.osv):
    _name = 'hr.emppay.sheet'
    _description = 'Payroll'
    _columns = {
        'name': fields.char('Reference', size=64, required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('verified', 'Verified'),
            ('paid', 'Paid'),
        ], 'Status', select=True, readonly=True),
        'date_from': fields.date('Date From', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_to': fields.date('Date To', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'emppay_ids': fields.one2many('hr.emppay', 'emppay_sheet_id', 'Payslips', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'attend_month_id': fields.many2one('hr.rpt.attend.month', 'Attendance Report'),
        'note': fields.text('Description', readonly=True, states={'draft':[('readonly',False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=False, readonly=True, states={'draft': [('readonly', False)]}),
    }
    _defaults = {
        'state': 'draft',
        'date_from': lambda *a: time.strftime('%Y-%m-01'),
        'date_to': lambda *a: str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10],
        'company_id': lambda self, cr, uid, context: \
                self.pool.get('res.users').browse(cr, uid, uid,
                    context=context).company_id.id,
    }
    
    def create(self, cr, uid, values, context=None):
        if not 'name' in values or values['name'] == '':
            name = self.pool.get('ir.sequence').get(cr, uid, 'emppay.payroll')
            if values['attend_month_id']:
                attendance_name = self.pool.get('hr.rpt.attend.month').read(cr, uid, values['attend_month_id'], ['name'], context=context)['name']
                if attendance_name:
                    name += '-' + attendance_name
            values['name'] = name
        new_id = super(hr_emppay_sheet,self).create(cr, uid, values, context=context)
        return new_id
    
    def unlink(self, cr, uid, ids, context=None):
        for rpt in self.read(cr, uid, ids, ['state'], context=context):
            if rpt['state'] not in ('draft'):
                raise osv.except_osv(_('Error'),_('Only order with Draft state can be delete!'))
        
        return super(hr_emppay_sheet, self).unlink(cr, uid, ids, context=context)
        
    def action_draft(self, cr, uid, ids, context=None):
        return self._set_state(cr, uid, ids, 'draft', context)

    def action_verify(self, cr, uid, ids, context=None):
        return self._set_state(cr, uid, ids, 'verified', context)
    
    def action_pay(self, cr, uid, ids, context=None):
        return self._set_state(cr, uid, ids, 'paid', context)
            
    def _set_state(self, cr, uid, ids, state, context=None):
        return self.write(cr, uid, ids, {'state': state}, context=context)
        emppay_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            emppay_ids += [emppay.id for emppay in order.emppay_ids]
        self.pool.get('hr.emppay').write(cr, uid, emppay_ids, {'state':state}, context=context)
        return True
            
    def add_from_att_report(self, cr, uid, ids, context=None):
        order = self.browse(cr,uid,ids[0],context=context)
        if not order.attend_month_id:
            raise osv.except_osv(_('Invalid Action!'), _('Please set the Attendance Report first.'))
        payroll = self.browse(cr, uid, ids[0], context=context)
        unlink_slip_ids = [slip.id for slip in payroll.emppay_ids]
        self.pool.get('hr.emppay').unlink(cr, uid, unlink_slip_ids, context=context)
        return self.pool.get('hr.rpt.attend.month').add_payroll(cr, uid, order.attend_month_id.id, ids[0], remove_old_slips = False, context=context)        
    
#    def add_from_att_record(self, cr, uid, ids, context=None):
#        return self.write(cr, uid, ids, {'state': 'close'}, context=context)        
    def _pdf_data(self, cr, uid, ids, form_data, context=None):
        return {'xmlrpt_name': 'hr.rpt.attend.month'}
    
    '''
    def print_slip(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids[0], context=context)
        datas = {
                 'model': self._name,
                 'ids': [ids[0]],
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'hr.emppay.sheet.slip', 'datas': datas, 'nodestroy': True} 
    '''
    
    def print_sheet_slip(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        order = self.browse(cr, uid, ids[0], context=context)
        emppay_ids = [emppay.id for emppay in order.emppay_ids]
        return self.pool.get('hr.emppay').print_slip(cr, uid, emppay_ids, context=context)
    
hr_emppay_sheet()
'''
from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext
class payslip_print(rml_parser_ext):
    def __init__(self, cr, uid, name, context):
        super(payslip_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'list_alw':self.list_alw,
            'list_ded':self.list_ded,
        })
    def list_alw(self,slip):
        ret = ''
        for alw in slip.alw_ids:
            ret += '%s: %s; '%(alw.name,alw.amount)
        return ret
    def list_ded(self,slip):
        ret = ''
        for item in slip.ded_ids:
            ret += '%s: %s; '%(item.name,item.amount)
#        ret += '%s: %s'%(u'社保(SI)',slip.si_total_personal)
        return ret
'''    
#report_sxw.report_sxw('report.hr.emppay.sheet.slip', 'hr.emppay.sheet', 'addons/metro_hr/emppay/hr_emppay_sheet_slip.rml', parser=payslip_print, header='internal landscape')

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
        'emppay_id': fields.many2one('hr.emppay', 'Payslip', required=True, select=True, ondelete='cascade'),
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
        'emppay_id': fields.many2one('hr.emppay', 'Payslip', required=True, select=True, ondelete='cascade'),
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

    def _wage_all(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for slip in self.browse(cr, uid, ids, context=context):
            wage_attend = 0.0
            wage_ot = 0.0
            if slip.days_work and slip.days_work != 0:
                wage_attend = slip.wage*slip.days_attend/slip.days_work
                
                wage_hourly = slip.wage/slip.days_work/8.0
                wage_ot = wage_hourly * slip.hours_ot
                wage_ot_we = wage_hourly * slip.hours_ot_we * 2
                wage_ot_holiday = wage_hourly * slip.hours_ot_holiday * 3
                wage_ot_total = wage_ot + wage_ot_we + wage_ot_holiday
                
                wage_work = wage_attend + wage_ot_total
            
            alw_total = 0.0
            for alw in slip.alw_ids:
                alw_total += alw.amount
                
            ded_total = 0.0
            for ded in slip.ded_ids:
                ded_total += ded.amount
                
            si_total_personal = 0.0
            si_total_company = 0.0
            for si in slip.si_ids:
                si_total_personal += si.amount_personal
                si_total_company += si.amount_company
                
            wage_total = wage_attend + wage_ot + alw_total
            wage_pay = wage_total - ded_total - si_total_personal
            wage_tax = wage_total - si_total_personal
            
            pit = max([
                        (wage_tax - slip.contract_id.pit_base)*rate[0]-rate[1] 
                        for rate in [(0.03, 0), (0.1, 105), (0.2, 555), (0.25, 1005), (0.3, 2755), (0.35, 5505), (0.45, 13505)]
                        ])
            pit = max([pit,0])
            
            wage_net = wage_pay - pit
                        
            '''
            The reason use 'month_attend_days_law' is that the days_attends is based on the month_attend_days_law
            see below code in hr_rpt_attend_month:
                days_attend2 = days_attend2/days_work2*month_attend_days_law
            '''
            month_attend_days_law = slip.company_id.month_attend_days_law                            
            wage_attend2 = slip.wage2*slip.days_attend2/month_attend_days_law
            
            wage_hourly2 = slip.wage2/month_attend_days_law/8.0
            wage_ot2 = wage_hourly2 * slip.hours_ot2
            wage_ot_we2 = wage_hourly2 * slip.hours_ot_we2 * 2
            wage_ot_holiday2 = wage_hourly2 * slip.hours_ot_holiday2 * 3
            wage_ot_total2 = wage_ot2 + wage_ot_we2 + wage_ot_holiday2

            wage_bonus2 = wage_attend + wage_ot - wage_attend2 - wage_ot2
            wage_work2 = wage_attend2 + wage_ot2 + wage_bonus2
            
            res[slip.id].update({'wage_attend':wage_attend,
                               'wage_ot':wage_ot,
                               'wage_ot_we':wage_ot_we,
                               'wage_ot_holiday':wage_ot_holiday,
                               'wage_ot_total':wage_ot_total,
                               'wage_work':wage_work,
                               'alw_total':alw_total,
                               'wage_total':wage_total,
                               'ded_total':ded_total,
                               'si_total_personal':si_total_personal,                               
                               'si_total_company':si_total_company,
                               
                               'wage_pay':wage_pay,
                               
                               'wage_tax':wage_tax,
                               'pit':pit,
                               
                               'wage_net':wage_net,  
                               
                               'wage_attend2':wage_attend2, 
                               'wage_ot2':wage_ot2,
                               'wage_ot_we2':wage_ot_we2,
                               'wage_ot_holiday2':wage_ot_holiday2,
                               'wage_ot_total2':wage_ot_total2,
                               'wage_bonus2':wage_bonus2,  
                               'wage_work2':wage_work2,
                               })              
        return res
    
    _columns = {
        'name': fields.char('Reference', size=64, required=False, readonly=True, states={'draft': [('readonly', False)]}),   
        'employee_id': fields.many2one('hr.employee', 'Employee', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'contract_id': fields.many2one('hr.contract', 'Contract', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_from': fields.date('Date From', readonly=True, states={'draft': [('readonly', False)]}, required=True),
        'date_to': fields.date('Date To', readonly=True, states={'draft': [('readonly', False)]}, required=True),        
        
        #Below from employee contract, 数据为只读
        #contract.wage
        'wage':fields.float('Contract Wage', digits_compute=dp.get_precision('Payroll')),
        #contract.wage2
        'wage2':fields.float('Contract Wage2', digits_compute=dp.get_precision('Payroll')),     
        #attendance report line id
        'attend_id':fields.many2one('hr.rpt.attend.month.line', 'Attendance'),
        
        #Below from attend data, user can change, 数据为只读
        'days_work': fields.related('attend_id','days_work',type='float',string='Work Days',  readonly=True), #attend_line_id.days_work
        'days_attend': fields.related('attend_id','days_attend',type='float',string='Days Attended',  readonly=True),#attend_line_id.days_attend
        'hours_ot': fields.related('attend_id','hours_ot',type='float',string='Hours OT(Normal)',  readonly=True),#attend_line_id.hours_ot
        'hours_ot_we': fields.float('Hours OT(Week End)', readonly=True),#0
        'hours_ot_holiday': fields.float('Hours OT(Law Holiday)', readonly=True), #0
        #Below from attend data, user can change, 数据为只读, 下面相关字段的显示使用组来限制
        'days_work2': fields.related('attend_id','days_work2',type='float',string='Work Days2',  readonly=True), #attend_line_id.days_work2
        'days_attend2': fields.related('attend_id','days_attend2',type='float',string='Days Attended2',  readonly=True),#attend_line_id.days_attend2
        'hours_ot2': fields.related('attend_id','hours_ot2_nonwe',type='float',string='Hours OT(Normal)2',  readonly=True),#attend_line_id.hours_ot2_nonwe
        'hours_ot_we2': fields.related('attend_id','hours_ot2_we',type='float',string='Hours OT(Week End)2',  readonly=True),#attend_line_id.hours_ot2_we
        'hours_ot_holiday2': fields.float('Hours OT(Law Holiday)', readonly=True), #0   
        
        #copy from contract_id.alwded_ids
        'alw_ids': fields.one2many('hr.emppay.ln.alwded', 'emppay_id', 'Allowance', required=False, readonly=True, 
                                   states={'draft': [('readonly', False)]}, domain=[('type','=','alw')]),
        'ded_ids': fields.one2many('hr.emppay.ln.alwded', 'emppay_id', 'Deduction', required=False, readonly=True, 
                                   states={'draft': [('readonly', False)]}, domain=[('type','=','ded')]),
        #copy from contract_id.si_ids
        'si_ids': fields.one2many('hr.emppay.ln.si', 'emppay_id', 'Social Insurance', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        
        #wage items, calculated based on atttendance, wage, alw_ids, ded_ids, si_ids        
        'wage_attend':fields.function(_wage_all, string='Wage(attend)', type='float', store=True,
                                      digits_compute=dp.get_precision('Payroll'), multi="_wage_all"), 
        'wage_ot':fields.function(_wage_all, string='Wage(OT)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_ot_we':fields.function(_wage_all, string='Wage(OT Weekend)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_ot_holiday':fields.function(_wage_all, string='Wage(OT Holiday)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),                
        'wage_ot_total':fields.function(_wage_all, string='Wage(OT Total)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Wage(OT) + Wage(OT Weekend) + Wage(OT Holiday)"),
        'wage_work':fields.function(_wage_all, string='Wage(Work)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Wage(attend) + Wage(OT)"),
        'alw_total':fields.function(_wage_all, string='Allowance', type='float',  store=True,
                                    digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #wage_attend + wage_ot + alw_total
        'wage_total':fields.function(_wage_all, string='Wage(total)', type='float',  store=True,
                                     digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                     help="Wage(attend) + Wage(OT) + Allowance"),
        'ded_total':fields.function(_wage_all, string='Deduction', type='float',  store=True,
                                    digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'si_total_personal':fields.function(_wage_all, string='SI(Personal)', type='float',  store=True,
                                            digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'si_total_company':fields.function(_wage_all, string='SI(Company)', type='float',  store=True,
                                           digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #wage_attend + wage_ot + alw_total - ded_total - si_total_personal
        'wage_pay':fields.function(_wage_all, string='Wage(Pay)', type='float',  store=True,
                                     digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                     help="Wage(total) - Deduction - SI(Personal)"),
        #wage_attend + wage_ot + alw_total - si_total_personal
        'wage_tax':fields.function(_wage_all, string='Wage(for tax)', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                     help="Wage(total) - SI(Personal)"),
        'pit':fields.function(_wage_all, string='PIT', type='float',  store=True,
                              digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #wage_total - PIT
        'wage_net':fields.function(_wage_all, string='Wage(Net)', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                     help="Wage(Pay) - PIT"),  
                       
        'wage_attend2':fields.function(_wage_all, string='Wage(attend)2', type='float', store=True,
                                      digits_compute=dp.get_precision('Payroll'), multi="_wage_all"), 

        'wage_ot2':fields.function(_wage_all, string='Wage(OT)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_ot_we2':fields.function(_wage_all, string='Wage(OT Weekend)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_ot_holiday2':fields.function(_wage_all, string='Wage(OT Holiday)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),                
        'wage_ot_total2':fields.function(_wage_all, string='Wage(OT Total)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Wage(OT)2 + Wage(OT Weekend)2 + Wage(OT Holiday)2"),
        'wage_bonus2':fields.function(_wage_all, string='Wage(Bonus)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_work2':fields.function(_wage_all, string='Wage(Work)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Wage(attend)2 + Wage(OT)2 + Wage(Bonus)2"),                                             
                
        'state': fields.selection([
            ('draft', 'Draft'),
            ('verified', 'Verified'),
            ('paid', 'Paid'),
        ], 'Status', select=True, readonly=True,
            help='* When the payslip is created the status is \'Draft\'.\
            \n* If the payslip is verified, the status is \'Verified\'. \
            \n* If the payslip is paid then status is set to \'Paid\'.'),
        'company_id': fields.many2one('res.company', 'Company', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'note': fields.text('Description', readonly=True, states={'draft':[('readonly',False)]}),
        'emppay_sheet_id': fields.many2one('hr.emppay.sheet', 'Payroll', readonly=True, states={'draft': [('readonly', False)]}, ondelete='cascade'),
        
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

    def action_verify(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'verified'}, context=context)

    def action_pay(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'paid'}, context=context)

    def action_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.state not in  ['draft']:
                raise osv.except_osv(_('Warning!'),_('You cannot delete a payslip which is not draft!'))
        return super(hr_emppay, self).unlink(cr, uid, ids, context)
    def print_slip(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids, context=context)
        datas = {
                 'model': 'hr.emppay',
                 'ids': ids,
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'hr.emppay.slip', 'datas': datas, 'nodestroy': True} 
        
hr_emppay()

from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext
class emppay_slip_print(rml_parser_ext):
    def __init__(self, cr, uid, name, context):
        super(emppay_slip_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'list_alw':self.list_alw,
            'list_ded':self.list_ded,
        })
    def list_alw(self,slip):
        ret = ''
        for alw in slip.alw_ids:
            ret += '%s: %s; '%(alw.name,alw.amount)
        return ret
    def list_ded(self,slip):
        ret = ''
        for item in slip.ded_ids:
            ret += '%s: %s; '%(item.name,item.amount)
#        ret += '%s: %s'%(u'社保(SI)',slip.si_total_personal)
        return ret
    
report_sxw.report_sxw('report.hr.emppay.slip', 'hr.emppay', 'addons/metro_hr/emppay/hr_emppay_slip.rml', parser=emppay_slip_print, header='internal landscape')


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
