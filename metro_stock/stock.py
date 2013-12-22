# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from openerp import netsvc

from openerp.osv import fields,osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class material_request(osv.osv):
    _name = "material.request"
    _inherit = "stock.picking"
#    _table = "stock_picking"
    _description = "Material Request"

    _columns = {
        'dept_id': fields.many2one('hr.department', 'Department', states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}, required=True),
    }
    def create(self, cr, uid, vals, context=None):
        if vals.get('name','/')=='/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'material.request') or '/'
        order =  super(material_request, self).create(cr, uid, vals, context=context)
        return order
class material_request_line(osv.osv):
    _name = "material.request.line"
    _inherit = "stock.move"
#    _table = "stock_move"
    _description = "Material Request Line"

    _columns = {
        'user_id': fields.many2one('hr.employee','Requester',required=True),
        'sale_id': fields.char('Sales ID',size=8),
        'notes': fields.char('Reason and use',size=64),
        'dept_id': fields.related('picking_id','dept_id',string='Department',type='many2one',relation='hr.department',select=True),
        'date_order': fields.related('picking_id','date',string='Request Date',type='datetime'),
    }