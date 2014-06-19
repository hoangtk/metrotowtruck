# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv

class account_move(osv.osv):
    _inherit = "account.move"
    
    #set the internal_number to empty, then user can delete the invoice after user set invoice to draft from cancel state
    def review_account_move(self, cr, uid, ids, context=None):
        review_ids = self.search(cr, uid, [('id','in',ids),('state','=','posted')], context=context)
        self.write(cr, uid, review_ids, {'to_check':True},context=context)
        return True

    def button_validate(self, cr, uid, ids, context=None):
        unpost_ids = self.search(cr, uid, [('id','in',ids),('state','=','draft')], context=context)
        return super(account_move,self).button_validate(cr, uid, unpost_ids, context=context)
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: