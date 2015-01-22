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
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

from openerp import netsvc
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from openerp.tools.safe_eval import safe_eval as eval
    
class hr_contract(osv.osv):
    _inherit = 'hr.contract'
    _columns = {        
        #Wage currency
        'wage_currency_id': fields.many2one('res.currency', 'Wage Currency'),
    }

    def _get_currency(self, cr, uid, context=None):
        if context is None:
            context = {}
        cur = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id
        return cur and cur.id or False
        
    _defaults={
        'wage_currency_id': _get_currency
        }
    
class hr_emppay(osv.osv):
    _inherit = 'hr.emppay'
    '''
    Override this method, to share code between parent and child's function fields
    '''
    def _wage_compute(self, cr, uid, ids, field_names, args, context=None):
        resu = super(hr_emppay, self)._wage_compute(cr, uid, ids, field_names, args, context=None)
        curr_obj = self.pool.get('res.currency')
        for slip in self.browse(cr, uid, ids, context=context):
            slip_currency_id = slip.currency_id or slip.contract_id.wage_currency_id
            if slip_currency_id and slip_currency_id.id != slip.company_id.currency_id.id:
                curr_from_id = slip_currency_id.id
                curr_to_id = slip.company_id.currency_id.id
                wage_total_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['wage_total'], context=context)
                wage_pay_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['wage_pay'], context=context)
                wage_net_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['wage_net'], context=context)
                alw_total_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['alw_total'], context=context)
                ded_total_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['ded_total'], context=context)
                resu[slip.id].update({'show_local':True, 
                                      'wage_total_local':wage_total_local, 'wage_pay_local':wage_pay_local, 'wage_net_local':wage_net_local,
                                      'alw_total_local':alw_total_local, 'ded_total_local':ded_total_local})
            else:
                resu[slip.id].update({'show_local':False, 'wage_total_local':0.0, 'wage_pay_local':0.0, 'wage_net_local':0.0})        
        return resu
    '''
    this method is also defined in hr_emppay.py, but the method in function's field can not be inherited by reuse, so redefine it and do not call super
    Both the _wage_all in hr_emppay.py and this py file, will call same method _wage_compute(), override that method
    '''    
    def _wage_all(self, cr, uid, ids, field_names, args, context=None):
        return self._wage_compute(cr, uid, ids, field_names, args, context=context)
            
    _columns = {
        'currency_id':fields.related('contract_id', 'wage_currency_id', string="Currency", type='many2one',relation='res.currency',store=True),
        'show_local':fields.function(_wage_all, string='Show Local', type='boolean',  store=True, multi="_wage_all"),
        'wage_total_local':fields.function(_wage_all, string='Total Wage Local', type='float',  store=True,
                                     digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_pay_local':fields.function(_wage_all, string='Wage Should Pay Local', type='float',  store=True,
                                     digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_net_local':fields.function(_wage_all, string='Net Wage Local', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),  
        'alw_total_local':fields.function(_wage_all, string='Allowance Local', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),  
        'ded_total_local':fields.function(_wage_all, string='Deduction Local', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
    }
        
hr_emppay()

class hr_contract_alwded(osv.osv):
    _inherit = 'hr.contract.alwded'
    _columns = {
        'currency_id':fields.many2one('res.currency','Currency'),
    }
    
    def create(self, cr, uid, values, context=None):
        new_id = super(hr_contract_alwded,self).create(cr, uid, values, context=context)
        #update the currency_id to contract's wage currency, if user do not supply the currency
        if ('currency_id' not in values or not values['currency_id']) and values['contract_id']:
            currency_id = self.pool.get('hr.contract').read(cr, uid, values['contract_id'], ['wage_currency_id'], context=context)['wage_currency_id']
            self.write(cr, uid, new_id, {'currency_id':currency_id[0]}, context=context)
        return new_id

class hr_emppay_ln_alwded(osv.osv):
    _inherit = 'hr.emppay.ln.alwded'
    _columns = {
        'currency_id':fields.many2one('res.currency','Currency'),
        'amount_local':fields.float('Amount Local', digits_compute=dp.get_precision('Payroll')),
    }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
