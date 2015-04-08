# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 OpenERP SA (<http://www.openerp.com>)
#    Copyright (C) 2011-2013 Serpent Consulting Services Pvt. Ltd. (<http://www.serpentcs.com>).

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################

from openerp.osv import fields, osv
from osv import osv
from tools.translate import _
from openerp.tools.translate import _
from datetime import datetime

class future_shipment(osv.osv):
    '''
    Define one future shipment order, one shipment have multiple product lines
    '''
    _name="future.shipment"
    _columns = {
        'origin_id':fields.many2one('res.partner', 'Origination'),
        'dest_id': fields.many2one('res.partner','Destination'),
        'shipment_line':fields.one2many('future.shipment.line','shipment_id','Future Shipment Line'),
        'state':fields.selection(
                                 [('wait','Waiting'),('shipped','Shipped')],
                                 'State',required=True
                                 ),
        'line_ids' : fields.one2many('future.shipment.line','req_id','Products to future shipping',readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
    }
    
future_shipment()

class future_shipment_line(osv.osv):
    '''
    doc
    Model: future.shipment.line
    '''
    _name="future.shipment.line"
    _columns = {
        'line_ids' : fields.one2many('future.shipment.line','req_id','Products to future shipping',readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'req_id' : fields.many2one('future.shipment','Future Shipment Requisition', ondelete='cascade'),
        'shipment_id':fields.many2one('future.shipment','Shipment'),
        'product_id':fields.many2one('product.product', 'Product'),
        'product_qty': fields.integer('Quantity Of Products'),
        'notes':fields.text('The Description'),
    } 
future_shipment_line()
