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
    def _purchase_payments(self, cr, uid, ids, name, args, context=None):
        result = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            payments = []
            for order in invoice.purchase_ids:
                for payment in order.payment_ids:
                    payments.append(payment.id)
            result[invoice.id] = payments
        return result 

    def _compute_lines(self, cr, uid, ids, name, args, context=None):
        result = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            src = []
            lines = []
            if invoice.move_id:
                for m in invoice.move_id.line_id:
                    temp_lines = []
                    if m.reconcile_id:
                        #only include the account move with cash/bank journal and not related with so/po
                        temp_lines = map(lambda x: not x.purchase_ids and not x.sale_ids and x.journal_id.type in('cash','bank') and x.id, m.reconcile_id.line_id)
                    elif m.reconcile_partial_id:
                        #only include the account move with cash/bank journal and not related with so/po
                        temp_lines = map(lambda x: not x.purchase_ids and not x.sale_ids and x.journal_id.type in('cash','bank') and x.id, m.reconcile_partial_id.line_partial_ids)
#                    lines += [x for x in temp_lines if x not in lines]
                    lines += [x for x in temp_lines if (x and x not in lines)]
                    src.append(m.id)

            lines = filter(lambda x: x not in src, lines)
            
            result[invoice.id] = lines
        return result          
    _columns={
        'sale_ids': fields.many2many('sale.order', 'sale_order_invoice_rel', 'invoice_id', 'order_id', 'Sale Orders', readonly=True,),
        'sale_payment_ids': fields.function(_sale_payments, relation='account.move.line', type="many2many", string='Sale Payments'),
        'auto_reconcile_sale_pay': fields.boolean('Auto Reconcile Sale Payment',help='Auto reconcile the sale order payments when valid the invoice'),
        'purchase_ids': fields.many2many('purchase.order', 'purchase_invoice_rel', 'invoice_id', 'purchase_id', 'Purchase Orders', readonly=True,),
        'purchase_payment_ids': fields.function(_purchase_payments, relation='account.move.line', type="many2many", string='Purchase Payments'),
        'auto_reconcile_purchase_pay': fields.boolean('Auto Reconcile Purchase Payment',help='Auto reconcile the purchase order payments when valid the invoice'),
        #the invoice payment ids
        'payment_ids': fields.function(_compute_lines, relation='account.move.line', type="many2many", string='Payments'),
    }
    _defaults={'auto_reconcile_sale_pay':True,'auto_reconcile_purchase_pay':True}
    
    def invoice_validate(self, cr, uid, ids, context=None):
        res = super(account_invoice,self).invoice_validate(cr, uid, ids, context)
        #auto reconcile the invoices
        reconcile_ids = []
        for inv in self.browse(cr,uid,ids,context):
            if (inv.journal_id.type == 'sale' and inv.auto_reconcile_sale_pay) \
                or (inv.journal_id.type == 'purchase' and inv.auto_reconcile_purchase_pay) :
                reconcile_ids.append(inv.id)
        if len(reconcile_ids) > 0:
#            self.reconcile_sale_payment(cr, uid, reconcile_ids, inv.journal_id.type, context)
            self.reconcile_order_payment(cr, uid, reconcile_ids, inv.journal_id.type, context)
        return res    
    
    def reconcile_order_payment(self, cr, uid, ids, journal_type, context=None):
        context = context or {}
        move_line_pool = self.pool.get('account.move.line')
        for inv in self.browse(cr, uid, ids):
            if inv.journal_id.type != 'sale' and inv.journal_id.type != 'purchase':
                continue 
            inv_reconciled = False
            if not inv.move_id:
                continue
            #invoice move lines can do reconcile
            inv_move_line_ids = []
            #advance pay move lines with 'payable/receivable' can do reconcile
            rec_ids = []
            #advance pay move lines with 'pre payable/receivable acccount' can do reconcile
            prepay_rec_ids = []
            account_type = (inv.journal_id.type == 'sale' and 'receivable') or 'payable'
            #add the invoice 'receivable' move line
            for mv_ln in inv.move_id.line_id:
                #the sale/purchase invoice only have one receivable/payable move line 
                if mv_ln.account_id.type == account_type:
                    if mv_ln.reconcile_id:
                        inv_reconciled = True
                        break
                    inv_move_line_ids.append(mv_ln.id)
                    break
            if inv_reconciled or len(inv_move_line_ids) == 0:
                continue
            #add the advance sale payment move lines
            if inv.journal_id.type == 'sale':
                for pay in inv.sale_payment_ids:
                    if not pay.reconcile_id:
                        '''
                        if pay.account_id.id == inv.account_id.id:
                            #if use same account then do reconcile direct
                            rec_ids.append(pay.id)
                        else:
                            #use the prepayment account did the payments
                            prepay_rec_ids.append(pay.id)
                        '''
                        '''
                        #by johnw, 10/30/2014
                        if use rec_ids to reconcile directly:
                            if the account move line amount is difference between prepayment and invoice:
                                then both the prepay and invlice move lines will be partial reconcile,
                                then the invoice can not be set to 'paid' since its move lines is partial reconciled, not full reconciled
                                so all of will use prepay_rec_ids[] to generate one new account move, to make sure the invoice line full reconciled under this case.
                        ''' 
                        prepay_rec_ids.append(pay.id)
            if inv.journal_id.type == 'purchase':
                for pay in inv.purchase_payment_ids:
                    if not pay.reconcile_id:
                        '''
                        if pay.account_id.id == inv.account_id.id:
                            #if use same account then do reconcile direct
                            rec_ids.append(pay.id)
                        else:
                            #use the prepayment account did the payments
                            prepay_rec_ids.append(pay.id)
                        '''
                        '''
                        #by johnw, 10/30/2014
                        if use rec_ids to reconcile directly:
                            if the account move line amount is difference between prepayment and invoice:
                                then both the prepay and invlice move lines will be partial reconcile,
                                then the invoice can not be set to 'paid' since its move lines is partial reconciled, not full reconciled
                                so all of will use prepay_rec_ids[] to generate one new account move, to make sure the invoice line full reconciled under this case.
                        ''' 
                        prepay_rec_ids.append(pay.id)
            #reconcile the prepayments using prepayment account
            if len(prepay_rec_ids) > 0:
                self.add_inv_prepay_reconcile_move(cr,uid,inv,inv_move_line_ids,prepay_rec_ids,context)
            #reconcile the prepayments using payment account
            if len(rec_ids) > 0 :
                rec_ids.extend(inv_move_line_ids)
                move_line_pool.reconcile_partial(cr, uid, rec_ids, writeoff_acc_id=inv.account_id.id, writeoff_period_id=inv.period_id.id, writeoff_journal_id=inv.journal_id.id)
        return {'type': 'ir.actions.act_window_close'}
                                                           
    def add_inv_prepay_reconcile_move(self, cr, uid, inv, inv_move_line_ids, pay_move_line_ids, context=None):
        #1.generate one account move to reconcile the payments:debit-AP;credit-PrePay
        journal_obj = self.pool.get('account.journal')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        currency_obj = self.pool.get('res.currency')
        
        amount = inv.residual
        if amount < 0:
            return
        journal = inv.journal_id
        company = journal.company_id
        #########get the move##########
        date = fields.datetime.now()
        period_id = period_obj.find(cr, uid, dt=date, context=context)[0]
        period = period_obj.browse(cr, uid, period_id, context=context)
        move_name = self._get_payment_move_name(cr, uid, journal, period, context=None)
        move_description = ""
        if journal.type == 'sale':
            move_description = 'Customer invoice payments reconciliation between "%s" and "%s"'%('Account Receivable (Prepayment)', 'Account Receivable')
        else:
            move_description = 'Supplier invoice payments reconciliation between "%s" and "%s"'%('Account Payable (Prepayment)', 'Account Payable')
        move_line_name = 'Advance Payments Reconciliation'
        move_vals = {'name': move_name,
                'journal_id': journal.id,
                'date': date,
                'ref': inv.name,
                'period_id': period.id,
                'narration':move_description,
                }
        move_id = move_obj.create(cr, uid, move_vals, context=context)        
        #########get the move lines##########
        inv_debit_prefix = 0
        inv_credit_prefix = 0
        pay_debit_prefix = 0
        pay_credit_prefix = 0
        if journal.type == 'sale':
            #for the sales, record the paid amount to the debit 
            pay_debit_prefix = 1
            inv_credit_prefix = 1
        else:
            #for the purchase, record the paid amount to the credit 
            pay_credit_prefix = 1
            inv_debit_prefix = 1
            
        #the total need to reconcile
        amount_pay_total = 0.0
        move_lines = []
        move_line_vals = {}
        move_line_reconciles=[]
        #the payment reconcile lines
        for pay_mv_ln in move_line_obj.browse(cr,uid,pay_move_line_ids,context=context):
            can_reconcile, amount_pay = self.move_reconcile_info(cr,uid,pay_mv_ln,context)
            if can_reconcile:
                #set the payment reconcile amount
                #get the amount need to reconcine
                amount_need_allocate = amount - amount_pay_total
                if amount_need_allocate < amount_pay:
                    amount_pay = amount_need_allocate
                #get the currency info
                currency_id = False
                amount_currency = 0.0
                if journal.currency and journal.currency.id != company.currency_id.id:
                    currency_id = journal.currency.id
                    amount_currency, amount_pay = (amount_pay,
                                               currency_obj.compute(cr, uid,
                                                                    currency_id,
                                                                    company.currency_id.id,
                                                                    amount_pay,
                                                                    context=context))
                move_line_vals = \
                    {'name': move_line_name,
                    'debit': pay_debit_prefix*amount_pay,
                    'credit': pay_credit_prefix*amount_pay,
                    'account_id': pay_mv_ln.account_id.id,
                    'journal_id': inv.journal_id.id,
                    'period_id': period.id,
                    'partner_id': inv.partner_id.id,
                    'date': date,
                    'amount_currency': amount_currency,
                    'currency_id': currency_id,
                    'move_id':move_id,
                     }
                move_line_id = move_line_obj.create(cr,uid,move_line_vals,context=context)
                move_line_reconciles.append([pay_mv_ln.id,move_line_id])
                amount_pay_total += amount_pay
                if amount - amount_pay_total <=0:
                    break

        #the invoice reconcile lines
        amount_inv_total = 0.0
        for inv_mv_ln in move_line_obj.browse(cr,uid,inv_move_line_ids,context=context):
            can_reconcile, amount_inv = self.move_reconcile_info(cr,uid,inv_mv_ln,context)
            if can_reconcile:
                #get the amount need to reconcine
                amount_need_allocate = amount_pay_total - amount_inv_total
                if amount_need_allocate < amount_inv:
                    amount_inv = amount_need_allocate
                #get the currency info
                currency_id = False
                amount_currency = 0.0
                if journal.currency and journal.currency.id != company.currency_id.id:
                    currency_id = journal.currency.id
                    amount_currency, amount_inv = (amount_inv,
                                               currency_obj.compute(cr, uid,
                                                                    currency_id,
                                                                    company.currency_id.id,
                                                                    amount_inv,
                                                                    context=context))
                move_line_vals = \
                    {'name': move_line_name,
                    'debit': inv_debit_prefix*amount_inv,
                    'credit': inv_credit_prefix*amount_inv,
                    'account_id': inv_mv_ln.account_id.id,
                    'journal_id': inv.journal_id.id,
                    'period_id': period.id,
                    'partner_id': inv.partner_id.id,
                    'date': date,
                    'amount_currency': amount_currency,
                    'currency_id': currency_id,
                    'move_id':move_id,
                     }
                move_line_id = move_line_obj.create(cr,uid,move_line_vals,context=context)
                move_line_reconciles.append([inv_mv_ln.id,move_line_id])
                
                amount_inv_total += amount_inv
                if amount_pay_total - amount_inv_total <=0:
                    break   

        for reconciles in move_line_reconciles:
            move_line_obj.reconcile_partial(cr, uid, reconciles, writeoff_acc_id=inv.account_id.id, writeoff_period_id=inv.period_id.id, writeoff_journal_id=inv.journal_id.id)

    def _get_payment_move_name(self, cr, uid, journal, period, context=None):
        if context is None:
            context = {}
        seq_obj = self.pool.get('ir.sequence')
        sequence = journal.sequence_id

        if not sequence:
            raise osv.except_osv(
                _('Configuration Error'),
                _('Please define a sequence on the journal %s.') %
                journal.name)
        if not sequence.active:
            raise osv.except_osv(
                _('Configuration Error'),
                _('Please activate the sequence of the journal %s.') %
                journal.name)

        ctx = context.copy()
        ctx['fiscalyear_id'] = period.fiscalyear_id.id
        name = seq_obj.next_by_id(cr, uid, sequence.id, context=ctx)
        return name

    def move_reconcile_info(self,cr,uid,act_mv_ln,context=None):
        can_reconcile = False
        amount = 0.0
        if not act_mv_ln.reconcile_id:
            if not act_mv_ln.reconcile_partial_id:
                can_reconcile = True
                amount = act_mv_ln.amount_residual
            else:
                #if move is partial reconciled, then only the amount_residual is negative then this line is also need more lines to reconcile it
                if act_mv_ln.amount_residual > 0:
                    can_reconcile = True
                    amount = act_mv_ln.amount_residual      
        return can_reconcile, amount
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: