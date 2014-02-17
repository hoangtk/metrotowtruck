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
        'auto_reconcile_sale_pay': fields.boolean('Auto Reconcile Sale Payment',help='Auto reconcile the sale order payments when valid the invoice'),
    }
    _defaults={'auto_reconcile_sale_pay':True}
    
    def invoice_validate(self, cr, uid, ids, context=None):
        res = super(account_invoice,self).invoice_validate(cr, uid, ids, context)
        #auto reconcile the invoices
        reconcile_ids = []
        for inv in self.browse(cr,uid,ids,context):
            if inv.journal_id.type == 'sale' and inv.auto_reconcile_sale_pay:
                reconcile_ids.append(inv.id)
        if len(reconcile_ids) > 0:
            self.reconcile_sale_payment(cr, uid, reconcile_ids, context)
        return res    
    
    def reconcile_sale_payment(self, cr, uid, ids, context=None):
        context = context or {}
        move_line_pool = self.pool.get('account.move.line')
        for inv in self.browse(cr, uid, ids):
            inv_reconciled = False
            if not inv.move_id:
                continue
            rec_ids = []
            #add the invoice 'receivable' move line
            for mv_ln in inv.move_id.line_id:
                #the sale invoice only have one receivable move line 
                if mv_ln.account_id.type == 'receivable':
                    if mv_ln.reconcile_id:
                        inv_reconciled = True
                    rec_ids.append(mv_ln.id)
                    break
            if inv_reconciled or len(rec_ids) == 0:
                continue
            #add the advance sale payment move lines
            for pay in inv.sale_payment_ids:
                if not pay.reconcile_id:
                    rec_ids.append(pay.id)
            
            move_line_pool.reconcile_partial(cr, uid, rec_ids, writeoff_acc_id=inv.account_id.id, writeoff_period_id=inv.period_id.id, writeoff_journal_id=inv.journal_id.id)
        return {'type': 'ir.actions.act_window_close'}
                                    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: