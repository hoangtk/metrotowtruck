# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv

class account_invoice(osv.osv):
    _inherit = "account.invoice"
    def _sale_payments(self, cr, uid, ids, name, args, context=None):
        result = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            payments = []
            for so in invoice.sale_ids:
                for payment in so.payment_ids:
                    payments.append(payment.id)
            result[invoice.id] = payments
        return result    
    _columns={
        'sale_ids': fields.many2many('sale.order', 'sale_order_invoice_rel', 'invoice_id', 'order_id', 'Sale Orders', readonly=True,),
        'sale_payment_ids': fields.function(_sale_payments, relation='account.move.line', type="many2many", string='Payments'),
    }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: