# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
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

from openerp import netsvc
import time

from openerp.osv import osv,fields
from openerp.tools.translate import _

class stock_return_picking(osv.osv_memory):
    _inherit = 'stock.return.picking'
    _columns = {
        'reason' : fields.text('Return Reason',required=True),
    }
    def create_returns(self, cr, uid, ids, context=None):
        resu = super(stock_return_picking, self).create_returns(cr, uid, ids, context)
        domain = eval(resu['domain'])
        pick_id = domain[0][2][0]
        data = self.read(cr, uid, ids[0], context=context)
        pick_obj = self.pool.get("stock.picking")
        pick = pick_obj.browse(cr,uid,pick_id,context=context)
        note = pick.note and pick.note != '' and (pick.note + ';' + data["reason"]) or data["reason"]
        pick_obj.write(cr, uid, [pick_id], {'note':note})
        return resu
    def get_return_history(self, cr, uid, pick_id, context=None):
        """ 
         Get  return_history.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param pick_id: Picking id
         @param context: A standard dictionary
         @return: A dictionary which of values.
        """
        pick_obj = self.pool.get('stock.picking')
        pick = pick_obj.browse(cr, uid, pick_id, context=context)
        return_history = {}
        for m  in pick.move_lines:
            #use the function field return_qty direct
            return_history[m.id] = m.return_qty
        return return_history    
#note        

stock_return_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
