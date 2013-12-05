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
import openerp.addons.decimal_precision as dp

class pur_req_po_line(osv.osv_memory):
    _name = "pur.req.po.line"
    _rec_name = 'product_id'

    _columns = {
        'wizard_id' : fields.many2one('pur.req.po', string="Wizard"),
        'product_id': fields.many2one('product.product', 'Product' ,required=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        'product_uom_id': fields.many2one('product.uom', 'Product Unit of Measure',required=True),
        'date_required': fields.date('Date Required'),
        'inv_qty': fields.float('Inventory'),
    }

pur_req_po_line()


class pur_req_po(osv.osv_memory):
    _name = 'pur.req.po'
    _description = 'Requisition\'s Purchase Order'
    _columns = {
        'line_ids' : fields.one2many('pur.req.po.line', 'wizard_id', 'Prodcuts'),
        'partner_id': fields.many2one('res.partner', 'Supplier', required=True,domain=[('supplier', '=', True)]),
    }

    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary with default values for all field in ``fields``
        """
        result1 = []
        if context is None:
            context = {}
        res = super(pur_req_po, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        req_obj = self.pool.get('pur.req')
        req = req_obj.browse(cr, uid, record_id, context=context)
        if req:             
            for line in req.line_ids:
                if not line.generated_po:
                    result1.append({'product_id': line.product_id.id, 'product_qty': line.product_qty,'product_uom_id':line.product_uom_id.id, 
                                    'date_required': line.date_required,'inv_qty':line.inv_qty})
            res.update({'line_ids': result1})
        return res

    def view_init(self, cr, uid, fields_list, context=None):
        """
         Creates view dynamically and adding fields at runtime.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return: New arch of view with new columns.
        """
        if context is None:
            context = {}
        res = super(pur_req_po, self).view_init(cr, uid, fields_list, context=context)
        record_id = context and context.get('active_id', False)
        if record_id:
            req_obj = self.pool.get('pur.req')
            req = req_obj.browse(cr, uid, record_id, context=context)
            if req.state != 'confirmed':
                raise osv.except_osv(_('Warning!'), _("You may only generate purchase orders based on confirmed requisitions!"))
            valid_lines = 0
            for line in req.line_ids:
                if not line.generated_po:
                    valid_lines += 1
            if not valid_lines:
                raise osv.except_osv(_('Warning!'), _("No available products need to generate purchase order!"))
        return res
    
    def create_po(self, cr, uid, ids, context=None):
        active_ids = context and context.get('active_ids', [])
        record_id = context and context.get('active_id', False) or False
        data =  self.browse(cr, uid, ids, context=context)[0]
        self.pool.get('pur.req').make_purchase_order(cr, uid, active_ids, data.partner_id.id, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def create_returns(self, cr, uid, ids, context=None):
        """ 
         Creates return picking.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param ids: List of ids selected
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {} 
        record_id = context and context.get('active_id', False) or False
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        uom_obj = self.pool.get('product.uom')
        data_obj = self.pool.get('pur.req.po.line')
        act_obj = self.pool.get('ir.actions.act_window')
        model_obj = self.pool.get('ir.model.data')
        wf_service = netsvc.LocalService("workflow")
        pick = pick_obj.browse(cr, uid, record_id, context=context)
        data = self.read(cr, uid, ids[0], context=context)
        date_cur = time.strftime('%Y-%m-%d %H:%M:%S')
        set_invoice_state_to_none = True
        returned_lines = 0
        
#        Create new picking for returned products
        if pick.type =='out':
            new_type = 'in'
        elif pick.type =='in':
            new_type = 'out'
        else:
            new_type = 'internal'
        seq_obj_name = 'stock.picking.' + new_type
        new_pick_name = self.pool.get('ir.sequence').get(cr, uid, seq_obj_name)
        new_picking = pick_obj.copy(cr, uid, pick.id, {
                                        'name': _('%s-%s-return') % (new_pick_name, pick.name),
                                        'move_lines': [], 
                                        'state':'draft', 
                                        'type': new_type,
                                        'date':date_cur, 
                                        'invoice_state': data['invoice_state'],
        })
        
        val_id = data['product_return_moves']
        for v in val_id:
            data_get = data_obj.browse(cr, uid, v, context=context)
            mov_id = data_get.move_id.id
            new_qty = data_get.quantity
            move = move_obj.browse(cr, uid, mov_id, context=context)
            new_location = move.location_dest_id.id
            returned_qty = move.product_qty
            for rec in move.move_history_ids2:
                returned_qty -= rec.product_qty

            if returned_qty != new_qty:
                set_invoice_state_to_none = False
            if new_qty:
                returned_lines += 1
                new_move=move_obj.copy(cr, uid, move.id, {
                                            'product_qty': new_qty,
                                            'product_uos_qty': uom_obj._compute_qty(cr, uid, move.product_uom.id, new_qty, move.product_uos.id),
                                            'picking_id': new_picking, 
                                            'state': 'draft',
                                            'location_id': new_location, 
                                            'location_dest_id': move.location_id.id,
                                            'date': date_cur,
                })
                move_obj.write(cr, uid, [move.id], {'move_history_ids2':[(4,new_move)]}, context=context)
        if not returned_lines:
            raise osv.except_osv(_('Warning!'), _("Please specify at least one non-zero quantity."))

        if set_invoice_state_to_none:
            pick_obj.write(cr, uid, [pick.id], {'invoice_state':'none'}, context=context)
        wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
        pick_obj.force_assign(cr, uid, [new_picking], context)
        # Update view id in context, lp:702939
        model_list = {
                'out': 'stock.picking.out',
                'in': 'stock.picking.in',
                'internal': 'stock.picking',
        }
        return {
            'domain': "[('id', 'in', ["+str(new_picking)+"])]",
            'name': _('Returned Picking'),
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model': model_list.get(new_type, 'stock.picking'),
            'type':'ir.actions.act_window',
            'context':context,
        }

pur_req_po()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
