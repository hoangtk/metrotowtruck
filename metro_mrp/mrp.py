# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
class mrp_bom(osv.osv):
    _inherit = 'mrp.bom'
    
#    def open_bom(self, cr, uid, ids, context=None):
#        ir_model_data_obj = self.pool.get('ir.model.data')        
#        ir_model_data_id = ir_model_data_obj.search(cr, uid, [['model', '=', 'ir.ui.view'], ['name', '=', 'mrp_bom_form_view'], ['module', '=', 'mrp']], context=context)
#        if ir_model_data_id:
#            res_id = ir_model_data_obj.read(cr, uid, ir_model_data_id, fields=['res_id'])[0]['res_id']
##        grp_ids = self._attr_grp_ids(cr, uid, [ids[0]], [], None, context)[ids[0]]
##        ctx = {'open_attributes': True, 'attribute_group_ids': grp_ids}
#
#        return {
#            'name': 'BOM',
#            'view_type': 'form',
#            'view_mode': 'form',
#            'view_id': [res_id],
#            'res_model': self._name,
#            'context': context,
#            'type': 'ir.actions.act_window',
#            'nodestroy': True,
#            'target': 'new',
#            'res_id': ids and ids[0] or False,
#        }
    
#    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
#        if context and 'bom_tree_id' in context:
#            args.append(('id','=',context.get('bom_tree_id')))
#        resu = super(mrp_bom, self).search(cr, user, args, offset, limit, order, context, count)
#        
#        return resu