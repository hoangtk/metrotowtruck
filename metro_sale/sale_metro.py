# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp import netsvc

class SaleOrder(osv.osv):

    _inherit="sale.order"
    _name="sale.order"
    _columns={
        'checkbox':fields.boolean("Include Payment Information"),
        'contact_log_ids': fields.many2many('contact.log', 'oppor_contact_log_rel','oppor_id','log_id',string='Contact Logs', )  
    }
    _defaults={'checkbox':True}
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        state = self.pool.get('sale.order').read(cr, uid, id, ['state'],context=context)['state']
        if state == 'draft' or state == 'sent':
            return "Quote"
        else:
            return "SalesOrder"
    def print_quotation(self, cr, uid, ids, context=None):
        '''
        This function prints the sales order and mark it as sent, so that we can see more easily the next step of the workflow
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time'
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'sale.order', ids[0], 'quotation_sent', cr)
        datas = {
                 'model': 'sale.order',
                 'ids': ids,
                 'form': self.read(cr, uid, ids[0], context=context),
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'sale.agreement', 'datas': datas, 'nodestroy': True}        
SaleOrder()

class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    _columns = {
        'mto_design_id': fields.many2one('mto.design', 'Configuration'),
#        'serial_ids': fields.many2many('mttl.serials', 'sale_serial_rel','line_id','serials_id',string='Serials',),
    }
    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'mto_design_id': None,
            'serial_ids': None,
        })         
        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)                
     
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
