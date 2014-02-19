# -*- encoding: utf-8 -*-
from osv import fields,osv
#the ID for the purchase requisition and the material request
class sale_product(osv.osv):
    _name = "sale.product"
    _description = "Sale Product"
    _columns = {
        'name': fields.char('ID', size=32, required=True),
        'note': fields.char('Description', size=128, required=False),
    }
