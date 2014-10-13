# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv
    
class account_voucher(osv.osv):
    _inherit = "account.voucher"
    _columns={
              'receipt_number': fields.char('Receipt Number', size=64, help="The reference of this invoice as provided by the partner."),              
    }
    def action_move_line_create(self, cr, uid, ids, context=None):
        resu = super(account_voucher,self).action_move_line_create(cr, uid, ids, context=context)
        '''
        #remove the auto post, johnw, 10/11/2014
        move_pool = self.pool.get('account.move')
        for voucher in self.browse(cr, uid, ids, context=context):
            if voucher.move_id and voucher.move_id.state == 'draft':
                move_pool.post(cr, uid, [voucher.move_id.id], context={})
        '''
        return resu
r=account_voucher()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: