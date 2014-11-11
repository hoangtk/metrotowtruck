# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2012 OpenERP S.A. (<http://openerp.com>).
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

import threading
from openerp import pooler
from openerp.tools import mail
from openerp import SUPERUSER_ID
from openerp.osv import osv

def email_send_template(cr, uid, ids, email_vals, context=None):
    if 'email_template_name' in email_vals:
        threaded_email = threading.Thread(target=_email_send_template, args=(cr, uid, ids, email_vals, context))
        threaded_email.start()
    return True
def _email_send_template(cr, uid, ids, email_vals, context=None):       
    pool =  pooler.get_pool(cr.dbname)
    #As this function is in a new thread, i need to open a new cursor, because the old one may be closed
    new_cr = pooler.get_db(cr.dbname).cursor()
    #send email by template
    if 'email_template_name' in email_vals:
        email_tmpl_obj = pool.get('email.template')
        #check email user 
        if 'email_user_id' in email_vals:
            assignee = pool.get('res.users').browse(new_cr, uid, email_vals['email_user_id'], context=context)
            #only send email when user have email setup
            if not assignee.email:
                return False
        tmpl_ids = email_tmpl_obj.search(new_cr, uid, [('name','=',email_vals['email_template_name'])])
        if tmpl_ids:
            for id in ids:
                email_tmpl_obj.send_mail(new_cr, uid, tmpl_ids[0], id, force_send=True, context=context)
    #close the new cursor
    new_cr.close()
    return True    

def email_send_group(cr, uid, email_from, email_to, subject, body, email_to_group_id=False, context=None):
    if email_from and (email_to or email_to_group_id):
        threaded_email = threading.Thread(target=_email_send_group, args=(cr, uid, email_from, email_to, subject, body, email_to_group_id, context))
        threaded_email.start()
    return True

def _email_send_group(cr, uid, email_from, email_to, subject, body, email_to_group_ids=False, context=None):
    pool =  pooler.get_pool(cr.dbname)
    new_cr = pooler.get_db(cr.dbname).cursor()
    emails = []
    if email_to: emails.append(email_to)
    if email_to_group_ids: 
        #get the group user's addresses by group id
        group_obj = pool.get("res.groups")
        if not isinstance(email_to_group_ids, (list, int, long)):
            email_to_group_ids = long(email_to_group_ids)
        #we can use SUPERUSER_ID to ignore the record rule for res_users and res_partner,  the email should send to all users in the group.
#        group = group_obj.browse(new_cr,SUPERUSER_ID,email_to_group_id,context=context)
        if isinstance(email_to_group_ids, (int, long)):
            email_to_group_ids = [email_to_group_ids]
        groups = group_obj.browse(new_cr,uid,email_to_group_ids,context=context)
        emails = []
        for group in groups:
            emails += [user.email for user in group.users if user.email]
    if emails:
        mail.email_send(email_from, emails, subject, body)
    #close the new cursor
    new_cr.close()        
    return True    

class msg_tool(osv.TransientModel):
    _name = 'msg.tool'
    #msg_vals = {'subject':'111','body':'111222333444555','model':'purchase.order','res_id':1719}
    def send_msg(self, cr, uid, user_ids, msg_vals, unread = False, starred = False, group_ids = None, context=None):
        """ Process the wizard content and proceed with sending the related
            email(s), rendering any template patterns on the fly if needed. """
        if not user_ids and not group_ids:
            return None
        if context is None:
            context = {}        
        if user_ids is None:
            user_ids = []
        #fetch users from group
        if group_ids:
            groups = self.pool.get('res.groups').browse(cr, uid, group_ids, context=context)
            add_user_ids = []
            for group in groups:
                add_user_ids = [u.id for u in group.users]
            user_ids += add_user_ids
        #get partners
        users = self.pool.get('res.users').browse(cr, uid, user_ids, context=context)
        partner_ids = [u.partner_id.id for u in users]
        
        msg_vals['partner_ids'] = partner_ids
        # post the message
        subtype = 'mail.mt_comment'
        msg_id = self.pool.get('mail.thread').message_post(cr, uid, [0], type='comment', subtype=subtype, context=context, **msg_vals)
        upt_vals = {}
        if 'model' in msg_vals:
            upt_vals['model'] = msg_vals['model']
        if 'res_id' in msg_vals:
            upt_vals['res_id'] = msg_vals['res_id']
        if upt_vals:
            self.pool.get('mail.message').write(cr, uid, [msg_id], upt_vals, context=context)
        #set unread and star flag
        if unread:
            for user_id in user_ids:
                self.pool.get("mail.message").set_message_read(cr, user_id, [msg_id], False, context=context)
        if starred:
            for user_id in user_ids:
                self.pool.get("mail.message").set_message_starred(cr, user_id, [msg_id], True, context=context)

        return msg_id
    
    def test_msg(self,cr,uid,ids,context=None):
        (model, mail_group_id) = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_purchase', 'group_pur_req_manager')
        user_ids = [uid,37]
        group_ids=[mail_group_id]      
        msg_vals = {'subject':'Order approve','body':'Please help approve the purchase order','model':'purchase.order','res_id':1719}
        
        msg_tool = self.pool.get('msg.tool')
        msg_id = msg_tool.send_msg(cr, uid, [uid,37],msg_vals,unread=True,starred=True,group_ids=[mail_group_id],context=context)        

        '''
        #fetch users from group
        if group_ids:
            groups = self.pool.get('res.groups').browse(cr, uid, group_ids, context=context)
            add_user_ids = []
            for group in groups:
                add_user_ids = [u.id for u in group.users]
            user_ids += add_user_ids
        #get partners
        users = self.pool.get('res.users').browse(cr, uid, user_ids, context=context)
        partner_ids = [u.partner_id.id for u in users]
        msg_vals['partner_ids'] = partner_ids
               
        msg_id = self.pool.get('purchase.order').message_post(cr, uid, 1719, **msg_vals)
                        
        #set unread and star flag
        for user_id in user_ids:
            self.pool.get("mail.message").set_message_read(cr, user_id, [msg_id], False, context=context)
        for user_id in user_ids:
            self.pool.get("mail.message").set_message_starred(cr, user_id, [msg_id], True, context=context)
        '''
                                        
        print msg_id    
        

def field_get_file(self, cr, uid, ids, field_names, args, context=None):
    result = dict.fromkeys(ids, {})
    attachment_obj = self.pool.get('ir.attachment')
    for obj in self.browse(cr, uid, ids):
        for field_name in field_names:
            result[obj.id][field_name] = None
            file_ids = attachment_obj.search(
                cr, uid, [('name', '=', field_name),
                          ('res_id', '=', obj.id),
                          ('res_model', '=', self._name)],context=context)
            if file_ids:
                result[obj.id][field_name] = attachment_obj.browse(cr, uid, file_ids[0]).datas
    return result

def field_set_file(self, cr, uid, id, field_name, value, args, context=None):
    attachment_obj = self.pool.get('ir.attachment')
    file_ids = attachment_obj.search(
        cr, uid, [('name', '=', field_name),
                  ('res_id', '=', id),
                  ('res_model', '=', self._name)])
    file_id = None
    if file_ids:
        file_id = file_ids[0]
        attachment_obj.write(cr, uid, file_id, {'datas': value})
    else:
        file_id = attachment_obj.create(
            cr, uid, {'name':  field_name,
                      'res_id': id,
                      'type': 'binary',
                      'res_model':self._name,
                      'datas': value})    
    return file_id        