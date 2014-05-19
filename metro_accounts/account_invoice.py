# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv

class account_invoice(osv.osv):
    _inherit = "account.invoice"
    
    #set the internal_number to empty, then user can delete the invoice after user set invoice to draft from cancel state
    def action_cancel(self, cr, uid, ids, context=None):
        resu = super(account_invoice,self).action_cancel(cr, uid, ids, context)
        self.write(cr, uid, ids, {'internal_number':False})
        return resu
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: