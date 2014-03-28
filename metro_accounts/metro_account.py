# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv
    
class account_account(osv.osv):
    _inherit = "account.account"
    _columns={
        'name': fields.char('Name', size=256, required=True, select=True, translate=True),           
    }
account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: