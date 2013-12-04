from osv import fields,osv

class SaleOrder(osv.osv):

    _inherit="sale.order"
    _name="sale.order"
    _columns={
        'checkbox':fields.boolean("Include Payment Information"),
    }
SaleOrder()


class Invoice(osv.osv):

    _inherit="account.invoice"
    _name="account.invoice"
    _columns={
        'check':fields.boolean("Include Payment Information"),
        'sale_order_ids': fields.many2many('sale.order', 'sale_order_invoice_rel', 'invoice_id', 'order_id', 'Sale Orders'),
    }
	
    def invoice_print(self, cursor, user, ids, context=None):
        res = super(Invoice, self).invoice_print(cursor, user, ids, context)
        res['report_name']='account.invoice.metro'
        return res

Invoice()

class CompanyConfiguration(osv.osv):

    _inherit="res.company"
    _name="res.company"
    _columns={
        'info':fields.text("Wire Transfer Information"),
    }   
        
CompanyConfiguration()
