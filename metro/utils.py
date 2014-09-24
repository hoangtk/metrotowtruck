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

def _email_send_group(cr, uid, email_from, email_to, subject, body, email_to_group_id=False, context=None):
    pool =  pooler.get_pool(cr.dbname)
    new_cr = pooler.get_db(cr.dbname).cursor()
    emails = []
    if email_to: emails.append(email_to)
    if email_to_group_id: 
        #get the group user's addresses by group id
        group_obj = pool.get("res.groups")
        if not isinstance(email_to_group_id, (int, long)):
            email_to_group_id = long(email_to_group_id)
        #we can use SUPERUSER_ID to ignore the record rule for res_users and res_partner,  the email should send to all users in the group.
#        group = group_obj.browse(new_cr,SUPERUSER_ID,email_to_group_id,context=context)
        group = group_obj.browse(new_cr,uid,email_to_group_id,context=context)
        emails = [user.email for user in group.users if user.email]
    if emails:
        mail.email_send(email_from, emails, subject, body)
    #close the new cursor
    new_cr.close()        
    return True    