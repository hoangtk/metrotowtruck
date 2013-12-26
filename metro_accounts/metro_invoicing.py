# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv
    
class account_invoice(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(account_invoice, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
        })
report_sxw.report_sxw(
    'report.account.invoice.metro',
    'account.invoice',
    'metro_accounts/account_invoice_metro.rml',
    parser=account_invoice
)
    
class account_voucher(osv.osv):
    _inherit = "account.voucher"
    _columns={
              'supplier_receipt_number': fields.char('Supplier Receipt Number', size=64, help="The reference of this invoice as provided by the supplier."),              
    }
r=account_voucher()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: