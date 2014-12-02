# -*- coding: utf-8 -*-

from openerp.osv import orm, fields
from openerp import tools

image_types = ['image', 'image_medium', 'image_small']

class product_product(orm.Model):
    _inherit = 'product.product'

    def _get_att_image(self, cr, uid, id, default_image_value=None,
                       write_image_value=None, context=None):
        '''
        Get the attachment image or create it
        @param id: id of product.product object
        @param defualt_image_value:  image data. when the attachement file is not exist
        system will create the file by this data.
        @param write_image_value:  image data, when the attachement file is exist
        system will write the file by this data.
        '''
        attachment_obj = self.pool.get('ir.attachment')
        dummy,  dir_product_image_id = self.pool.get('ir.model.data').get_object_reference(
            cr, uid, 'document', 'dir_product')
        result = {}
        if dir_product_image_id:
            for image_type in image_types:
                result[image_type] = None
                att_image_ids = attachment_obj.search(
                    cr, uid, [('name', '=', image_type + '.jpg'),
                              ('res_id', '=', id),
                              ('res_model', '=', 'product.product')])
                att_image_id = None
                if att_image_ids:
                    att_image_id = att_image_ids[0]
                    if write_image_value:
                        attachment_obj.write(
                            cr, uid, att_image_id, {'datas': tools.image_get_resized_images(
                                          write_image_value, return_big=True,
                                          avoid_resize_medium=True)[image_type]})

                if not att_image_ids and default_image_value:
                    att_image_id = attachment_obj.create(
                        cr, uid, {'name':  image_type + '.jpg',
                                  'res_id': id,
                                  'type': 'binary',
                                  'res_model': 'product.product',
                                  'datas': tools.image_get_resized_images(
                                      default_image_value, return_big=True,
                                      avoid_resize_medium=True)[image_type]})
                if att_image_id:
                    result[image_type] = attachment_obj.browse(cr, uid, att_image_id).datas
            # Clean the image field
            if result:
                self.write(cr, uid, id, {'image': None})
                return result
        return False

    def _get_image(self, cr, uid, ids, name, args, context=None):
        result = dict.fromkeys(ids, False)
        for obj in self.browse(cr, uid, ids):
            att_result = self._get_att_image(cr, uid, obj.id,
                                             default_image_value=obj.image,
                                             context=None)
            if att_result:
                result[obj.id] = att_result
            else:
                result[obj.id] = tools.image_get_resized_images(
                    obj.image, avoid_resize_medium=True)
        return result

    def _set_image(self, cr, uid, id, name, value, args, context=None):
        att_result = self._get_att_image(
            cr, uid, id, default_image_value=value, write_image_value=value, context=None)
        if att_result:
            return True
        return self.write(cr, uid, [id], {
            'image': tools.image_resize_image_big(value)}, context=context)


    _columns = {
        'image_medium': fields.function(_get_image, fnct_inv=_set_image,
            string="Medium-sized image", type="binary", multi="_get_image",
            help="Medium-sized image of the product. It is automatically "\
                 "resized as a 128x128px image, with aspect ratio preserved, "\
                 "only when the image exceeds one of those sizes. Use this field in form views or some kanban views."),
        'image_small': fields.function(_get_image, fnct_inv=_set_image,
            string="Small-sized image", type="binary", multi="_get_image",
            help="Small-sized image of the product. It is automatically "\
                 "resized as a 64x64px image, with aspect ratio preserved. "\
                 "Use this field anywhere a small image is required."),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
